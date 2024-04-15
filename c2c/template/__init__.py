# Copyright (c) 2011-2024, Camptocamp SA
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:

# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.

"""The template module."""

import copy
import itertools
import json
import logging
import os
import re
import subprocess  # nosec
import sys
import traceback
from argparse import ArgumentParser, Namespace
from string import Formatter
from subprocess import CalledProcessError  # nosec
from typing import Any, Callable, Optional, Protocol, Union, cast

import yaml
import yaml_include  # type: ignore
from yaml.parser import ParserError

Value = Union[str, int, float, dict[str, Any], list[Any]]

LOG = logging.getLogger(__name__)
DOT_SPLITTER_RE = re.compile(r"(?<!\\)\.")
ESCAPE_DOT_RE = re.compile(r"\\.")
INDEX_RE = re.compile(r"^\[([0-9]+)\]$")


def dot_split(string: str) -> list[str]:
    result = DOT_SPLITTER_RE.split(string)
    return [ESCAPE_DOT_RE.sub(".", i) for i in result if i != ""]


def transform_path(
    value: dict[str, Any],
    path: list[str],
    action: Callable[[str, str], Value],
    current_path: Optional[str] = "",
) -> None:
    assert len(path) > 0  # nosec
    key = path[0]
    if isinstance(value, list) and key == "[]":
        if len(path) == 1:
            for index, val in enumerate(value):
                value[index] = action(val, f"{current_path}[{index}]")
        else:
            for index, val in enumerate(value):
                transform_path(val, path[1:], action, f"{current_path}[{index}]")
    else:
        if isinstance(value, dict):
            if key not in value:
                LOG.warning(
                    "The key '%s' in '%s' is not present in: [%s]",
                    key,
                    current_path,
                    ", ".join([f"'{k}'" for k in value.keys()]),
                )
            else:
                if len(path) == 1:
                    value[key] = action(value[key], f"{current_path}.{path[0]}")
                else:
                    transform_path(value[key], path[1:], action, f"{current_path}.{path[0]}")

        elif isinstance(value, list):

            def replace(path, current_path, value, index):
                if index >= len(value):
                    LOG.warning(
                        "The key '%s' in '%s' is not present in: [%s]",
                        key,
                        current_path,
                        f"0..{len(value) - 1}",
                    )
                else:
                    if len(path) == 1:
                        value[index] = action(value[index], f"{current_path}[{index}]")
                    else:
                        transform_path(value[index], path[1:], action, f"{current_path}[{index}]")

            if path[0] == "[]":
                for index in range(len(value)):
                    replace(path, current_path, value, index)
            elif INDEX_RE.match(path[0]):
                index = int(INDEX_RE.match(path[0]).group(1))
                replace(path, current_path, value, index)
            else:
                LOG.warning("The key '%s' in '%s' is not valid for list", key, current_path)
        else:
            LOG.warning(
                "The value '%s' in '%s' is not valid, it should be a list or a dict", value, current_path
            )


def get_config(file_name: str) -> dict[str, Any]:
    with open(file_name, encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file.read())
    format_walker = FormatWalker(
        config["vars"], config.get("no_interpreted", []), config.get("environment", [])
    )
    format_walker()
    return do_process(config, format_walker.used_vars)


def main() -> None:
    logging.basicConfig(format="%(levelname)s:%(name)s:%(funcName)s:%(message)s")
    parser = ArgumentParser(description="Used to run a template")
    parser.add_argument(
        "--engine", "-e", choices=["jinja", "mako"], default="jinja", help="the used template engine"
    )
    parser.add_argument("--vars", "-c", help="the YAML file defining the variables")
    parser.add_argument("--cache", help="the generated cache file")
    parser.add_argument("--get-cache", help="generate a cache file")
    parser.add_argument("--section", action="store_true", help="use the section (template specific)")
    parser.add_argument("--files", nargs="*", help="the files to interpret")
    parser.add_argument(
        "--runtime-environment-pattern",
        help="Pattern used to format the runtime environment in interpreted files",
    )
    parser.add_argument("--get-vars", nargs="*", default=[], help="the vars to get, can be MY_VAR=my_var")
    parser.add_argument("--get-config", nargs="*", help="generate a configuration file")
    files_builder_help = (
        "generate some files from a source file (first ARG), "
        "to files (second ARG, with format we can access to the value attribute), "
        "and get the value on iter on the variable referenced by the third argument"
    )
    parser.add_argument("--files-builder", nargs=3, metavar="ARG", help=files_builder_help)
    options = parser.parse_args()
    do(options)


class FormatWalker:
    formatter = Formatter()

    def __init__(
        self,
        used_vars: dict[str, Any],
        no_interpreted: list[str],
        environment: list[dict[str, Any]],
        runtime_environment: Optional[list[dict[str, Any]]] = None,
        runtime_environment_pattern: Optional[str] = None,
    ):
        """Initialize the walker."""
        self.formatted: list[str] = []
        self.used_vars = used_vars
        self.no_interpreted = no_interpreted
        self.environment = environment
        self.runtime_environment = runtime_environment or []

        self.all_environment_dict = {}
        if runtime_environment_pattern is not None:
            for env in self.runtime_environment:
                if isinstance(env, str):
                    env = {"name": env}
                self.all_environment_dict[env["name"]] = runtime_environment_pattern.format(env["name"])

        for env in environment:
            if isinstance(env, str):
                env = {"name": env}

            if "default" in env:
                self.all_environment_dict[env["name"]] = os.environ.get(env["name"], env["default"])
            else:
                self.all_environment_dict[env["name"]] = os.environ[env["name"]]

    def path_in(self, path_list: list[str], list_: list[str]) -> bool:
        for path in path_list:
            if path in list_:
                return True
        return False

    def format_walker(
        self, current_vars: dict[str, Any], path: Optional[str] = None, path_list: Optional[list[str]] = None
    ) -> tuple[dict[str, Any], list[tuple[str, str]]]:
        if isinstance(current_vars, str):
            if path not in self.formatted:
                if self.path_in(path_list, self.no_interpreted):
                    self.formatted.append(path)
                    return current_vars, []
                attrs = self.formatter.parse(current_vars)
                for _, attr, _, _ in attrs:
                    if (
                        attr is not None
                        and attr not in self.formatted
                        and attr not in self.all_environment_dict
                    ):
                        return current_vars, [(path, attr)]
                self.formatted.append(path)
                vars_ = {}
                vars_.update(self.all_environment_dict)
                vars_.update(self.used_vars)
                return current_vars.format(**vars_), []
            return current_vars, []

        elif isinstance(current_vars, list):
            formatteds = []
            for index, var in enumerate(current_vars):
                new_path = f"{path}[{index}]"
                new_path_list = []
                assert path_list is not None  # nosec
                for _ in path_list:
                    new_path_list += [f"{path}[{index}]", f"{path}[]"]
                formatteds.append(self.format_walker(var, new_path, new_path_list))
            return [v for v, _ in formatteds], list(itertools.chain(*(s for _, s in formatteds)))

        elif isinstance(current_vars, dict):
            skip = []
            for key in current_vars.keys():
                if path is None:
                    current_path = key
                    current_path_list = [key]
                else:
                    current_path = f"{path}.{key}"
                    assert path_list is not None  # nosec
                    current_path_list = [f"{pl}.{key}" for pl in path_list]
                current_formatted = self.format_walker(current_vars[key], current_path, current_path_list)
                current_vars[key] = current_formatted[0]
                skip += current_formatted[1]
            return current_vars, skip
        else:
            self.formatted.append(path)

        return current_vars, []

    def __call__(self) -> None:
        skip: Optional[list[tuple[str, str]]] = None
        old_skip = sys.maxsize
        while skip is None or old_skip != len(skip) and len(skip) != 0:
            old_skip = sys.maxsize if skip is None else len(skip)
            self.used_vars, skip = self.format_walker(self.used_vars)

        if len(skip) > 0:
            LOG.error(
                "The following variable isn't correctly interpreted due missing dependency:\n%s",
                "\n".join([f"'{e[0]}' depend on '{e[1]}'" for e in skip]),
            )
            sys.exit(1)


def do(options: Namespace) -> None:  # pylint: disable=invalid-name
    if options.cache is not None and options.vars is not None:
        LOG.error("The --vars and --cache options cannot be used together")
        sys.exit(1)
    if options.cache is None and options.vars is None:
        LOG.error("One of the --vars or --cache options is required")
        sys.exit(1)

    if options.cache is not None:
        with open(options.cache, encoding="utf-8") as file_open:
            cache = json.loads(file_open.read())
            used_vars = cache["used_vars"]
            config = cache["config"]

        if options.files_builder is not None or options.files is not None:
            format_walker = FormatWalker(
                used_vars,
                config.get("no_interpreted", []),
                [],
                config.get("runtime_environment", []),
                options.runtime_environment_pattern,
            )
            format_walker()
            used_vars = format_walker.used_vars
    else:
        used_vars, config = read_vars(options.vars)

        format_walker = FormatWalker(
            used_vars,
            config.get("no_interpreted", []),
            config.get("environment", []),
            config.get("runtime_environment", []),
            (
                "{{{}}}"
                if options.get_config is not None or options.get_cache is not None
                else options.runtime_environment_pattern
            ),
        )
        format_walker()
        used_vars = format_walker.used_vars

    if options.get_cache is not None:
        cache = {
            "used_vars": used_vars,
            "config": config,
        }
        del cache["config"]["vars"]
        del cache["config"]["environment"]
        with open(options.get_cache, "wb") as file_open:
            file_open.write(json.dumps(cache).encode("utf-8"))

    for get_var in options.get_vars:
        corresp = get_var.split("=")
        if len(corresp) == 1:
            corresp = (get_var.upper(), get_var)

        if len(corresp) != 2:  # pragma: nocover
            LOG.error("The get variable '%s' has more than one '='", get_var)
            sys.exit(1)

        print(f"{corresp[0]}={used_vars[corresp[1]]!r}")

    if options.get_config is not None:
        new_vars: dict[str, Any] = {"vars": {}}
        for variable in options.get_config[1:]:
            var_path = variable.split(".")
            value = used_vars
            for key in var_path:
                if key in value:
                    value = value[key]
                else:
                    LOG.warning("The variable '%s' don't exists", variable)

            new_vars["vars"][variable] = value
        new_vars["environment"] = [
            {"name": env} if isinstance(env, str) else env for env in config.get("runtime_environment", [])
        ]
        new_vars["interpreted"] = config.get("runtime_interpreted", [])
        new_vars["postprocess"] = config.get("runtime_postprocess", [])
        new_vars["no_interpreted"] = config.get("no_interpreted", [])

        with open(options.get_config[0], "wb") as file_open:
            file_open.write(yaml.safe_dump(new_vars).encode("utf-8"))

    if options.files_builder is not None:
        var_path = options.files_builder[2].split(".")
        values = used_vars
        for key in var_path:
            values = values[key]

        if isinstance(values, dict):  # pragma: nocover
            for key, value in values.items():
                if isinstance(value, dict):
                    value.setdefault("name", key)
            values = values.values()

        elif not isinstance(values, list):  # pragma: nocover
            LOG.error("The variable '%s': '%s' should be an array", options.files_builder[2], values)
            sys.exit(1)

        for value in values:
            file_vars = {}
            file_vars.update(used_vars)
            file_vars.update(value)
            template = options.files_builder[0]
            destination = options.files_builder[1].format(**value)
            _proceed([(template, destination)], file_vars, options)

    if options.files is not None:
        files = [(f, ".".join(f.split(".")[:-1])) for f in options.files]
        _proceed(files, used_vars, options)


def get_path(value: dict[str, Any], path: str) -> tuple[tuple[Optional[dict[str, Any]], str], dict[str, Any]]:
    split_path = dot_split(path)
    parent = None
    for element in split_path:
        parent = value
        value = parent[element]
    return (parent, split_path[-1]), value


def set_path(item: tuple[dict[str, Any], str], value: str) -> None:
    parent, element = item
    parent[element] = value


def _proceed(files: list[tuple[str, str]], used_vars: dict[str, Any], options: Namespace) -> None:
    if options.engine == "jinja":
        from bottle import jinja2_template as engine  # type: ignore # pylint: disable=import-outside-toplevel

        bottle_template(files, used_vars, engine)

    elif options.engine == "mako":
        from bottle import mako_template as engine  # pylint: disable=import-outside-toplevel

        bottle_template(files, used_vars, engine)


class Engine(Protocol):
    def __call__(self, template: str, **kwargs: Any) -> str: ...


def bottle_template(files: list[tuple[str, str]], used_vars: dict[str, Any], engine: Engine) -> None:
    for template, destination in files:
        processed = engine(template, **used_vars)
        save(template, destination, processed)


def save(template: str, destination: str, processed: str) -> None:
    with open(destination, "wb") as file_open:
        file_open.write(processed.encode("utf-8"))
    os.chmod(destination, os.stat(template).st_mode)


def read_vars(vars_file: str) -> tuple[dict[str, Any], dict[str, Any]]:
    include_tag = yaml_include.Constructor(base_dir=os.path.dirname(vars_file))
    yaml.SafeLoader.add_constructor("!inc", include_tag)
    yaml.SafeLoader.add_constructor("!include", include_tag)
    with open(vars_file, encoding="utf-8") as file_open:
        used = cast(dict[str, Any], yaml.load(file_open.read(), yaml.SafeLoader))  # nosec

    used.setdefault("environment", [])
    used.setdefault("runtime_environment", [])
    used.setdefault("runtime_interpreted", {})
    used.setdefault("runtime_postprocess", [])

    current_vars: dict[str, Any] = {}
    if "extends" in used:
        current_vars, config = read_vars(used["extends"])

        no_interpreted = set()
        no_interpreted.update(config.get("no_interpreted", []))
        no_interpreted.update(used.get("no_interpreted", []))
        used["no_interpreted"] = list(no_interpreted)

        environment = config["environment"]
        runtime_environment = config["runtime_environment"]
        for env in used["runtime_environment"]:
            if env in environment:
                environment.remove(env)
            runtime_environment.append(env)
        for name, interpreted in config.get("runtime_interpreted", {}).items():
            if name in used["runtime_interpreted"]:
                if interpreted is list and used["runtime_interpreted"][name] is list:
                    used["runtime_interpreted"][name] += interpreted
                else:
                    value: dict[str, Any] = {"vars": []}
                    if interpreted is list:
                        value["vars"] += interpreted
                    else:
                        clone = copy.copy(interpreted)
                        if "vars" in clone:
                            value["vars"] += clone["vars"]
                            del clone["vars"]
                        value.update(clone)
                    if used["runtime_interpreted"][name] is list:
                        value["vars"] += used["runtime_interpreted"][name]
                    else:
                        clone = copy.copy(used["runtime_interpreted"][name])
                        if "vars" in clone:
                            value["vars"] += clone["vars"]
                            del clone["vars"]
                        value.update(clone)
            else:
                used["runtime_interpreted"][name] = interpreted
        used["runtime_postprocess"] += config.get("runtime_postprocess", [])
        for env in used["environment"]:
            if env in runtime_environment:
                runtime_environment.remove(env)
            environment.append(env)
        used["environment"] = environment
        used["runtime_environment"] = runtime_environment

    new_vars = do_process(used, used.get("vars", {}))

    update_paths = []
    for update_path in used.get("update_paths", []):
        split_path = update_path.split(".")
        for i in range(len(split_path)):
            update_paths.append(".".join(split_path[: i + 1]))
    update_vars(current_vars, new_vars, set(update_paths))
    return current_vars, used


def do_process(used: dict[str, Any], new_vars: dict[str, Any]) -> dict[str, Any]:
    globs = {
        "__builtins__": {},
        "__import__": __import__,
        "abs": abs,
        "all": all,
        "any": any,
        "bin": bin,
        "bool": bool,
        "bytearray": bytearray,
        "bytes": bytes,
        "chr": chr,
        "dict": dict,
        "enumerate": enumerate,
        "filter": filter,
        "float": float,
        "format": format,
        "frozenset": frozenset,
        "getattr": getattr,
        "hasattr": hasattr,
        "hash": hash,
        "hex": hex,
        "int": int,
        "isinstance": isinstance,
        "issubclass": issubclass,
        "iter": iter,
        "len": len,
        "list": list,
        "map": map,
        "max": max,
        "min": min,
        "next": next,
        "object": object,
        "oct": oct,
        "ord": ord,
        "pow": pow,
        "print": print,
        "property": property,
        "range": range,
        "repr": repr,
        "reversed": reversed,
        "round": round,
        "slice": slice,
        "sorted": sorted,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "type": type,
        "zip": zip,
    }
    if "interpreted" in used:
        interpreters = []
        for key, interpreter in used["interpreted"].items():
            if isinstance(interpreter, dict):
                interpreter["name"] = key
                if "priority" not in interpreter:
                    interpreter["priority"] = 0 if key in ["json", "yaml"] else 100
            else:
                interpreter = {
                    "name": key,
                    "vars": interpreter,
                    "priority": 0 if key in ["json", "yaml"] else 100,
                }
            interpreters.append(interpreter)

        interpreters.sort(key=lambda v: -v["priority"])  # type: ignore

        class CmdAction:
            def __init__(self, interpreter: dict[str, Any]):
                self.interpreter = interpreter
                self.ignore_error = self.interpreter.get("ignore_error", False)

            def __call__(self, expression: str, current_path: str) -> Value:
                cmd = interpreter["cmd"][:]  # [:] to clone
                cmd.append(expression)
                try:
                    with open(os.devnull, "w", encoding="utf-8") as dev_null:
                        return subprocess.run(  # nosec
                            cmd,
                            stderr=dev_null if self.ignore_error else None,
                            check=True,
                            stdout=subprocess.PIPE,
                            encoding="utf-8",
                        ).stdout.strip("\n")
                except (OSError, CalledProcessError) as exception:  # pragma: nocover
                    error = f"When running the expression '{expression}' in '{current_path}': {exception}"
                    LOG.error(error)
                    if self.ignore_error:
                        return "ERROR: " + error
                    else:
                        sys.exit(1)

        class PythonAction:
            def __init__(self, interpreter: dict[str, Any]):
                self.interpreter = interpreter

            def __call__(self, expression: str, current_path: str) -> Value:  # type: ignore
                try:
                    return cast(Value, eval(expression, globs))  # nosec # pylint: disable=eval-used
                except Exception:  # pragma: nocover # pylint: disable=broad-except
                    error = "When evaluating {} expression '{}' in '{}' as Python:\n{}".format(
                        var_name, expression, current_path, traceback.format_exc()
                    )
                    LOG.error(error)
                    if interpreter.get("ignore_error", False):
                        return "ERROR: " + error
                    else:
                        sys.exit(1)

        class BashAction:
            def __init__(self, interpreter: dict[str, Any]):
                self.interpreter = interpreter

            def __call__(self, expression: str, current_path: str) -> Value:
                try:
                    return subprocess.run(  # nosec
                        expression, shell=True, check=True, stdout=subprocess.PIPE, encoding="utf-8"
                    ).stdout.strip("\n")
                except (OSError, CalledProcessError) as exception:  # pragma: nocover
                    error = f"When running the expression '{expression}' in [{current_path}]: {exception}"
                    LOG.error(error)
                    if interpreter.get("ignore_error", False):
                        return "ERROR: " + error
                    else:
                        sys.exit(1)

        class JsonAction:
            def __init__(self, interpreter: dict[str, Any]):
                self.interpreter = interpreter

            def __call__(self, value: str, current_path: str) -> Value:
                try:
                    return cast(dict[str, Any], json.loads(value))
                except ValueError as exception:  # pragma: nocover
                    error = "When evaluating {} expression '{}' in '{}' as JSON: {}".format(
                        key, value, current_path, exception
                    )
                    LOG.error(error)
                    if interpreter.get("ignore_error", False):
                        return "ERROR: " + error
                    else:
                        sys.exit(1)

        class YamlAction:
            def __init__(self, interpreter: dict[str, Any]):
                self.interpreter = interpreter

            def __call__(self, value: str, current_path: str) -> Value:
                try:
                    return cast(dict[str, Any], yaml.safe_load(value))
                except ParserError as exception:  # pragma: nocover
                    error = "When evaluating {} expression '{}' in '{}' as YAML: {}".format(
                        key, value, current_path, exception
                    )
                    LOG.error(error)
                    if self.interpreter.get("ignore_error", False):
                        return "ERROR: " + error
                    else:
                        sys.exit(1)

        for interpreter in interpreters:
            for var_name in interpreter["vars"]:
                if "cmd" in interpreter:
                    action: Callable[[str, str], Value] = CmdAction(interpreter)
                elif interpreter["name"] == "python":
                    action = PythonAction(interpreter)
                elif interpreter["name"] == "bash":
                    action = BashAction(interpreter)
                elif interpreter["name"] == "json":
                    action = JsonAction(interpreter)
                elif interpreter["name"] == "yaml":
                    action = YamlAction(interpreter)
                else:  # pragma: nocover
                    LOG.error("Unknown interpreter name '%s'", interpreter["name"])
                    sys.exit(1)

                try:
                    transform_path(new_vars, dot_split(var_name), action)
                except KeyError:  # pragma: nocover
                    LOG.error("Expression for key not found: %s", var_name)
                    sys.exit(1)

    class PostprocessAction:
        def __init__(self, postprocess: dict[str, Any]) -> None:
            self.postprocess = postprocess

        def __call__(self, value: str, current_path: str) -> Value:  # type: ignore
            expression = self.postprocess["expression"]  # [:] to clone
            expression = expression.format(repr(value))
            try:
                return cast(Value, eval(expression, globs))  # nosec # pylint: disable=eval-used
            except ValueError as exception:  # pragma: nocover
                error = "When interpreting the expression '{}' in '{}': {}".format(
                    expression, current_path, exception
                )
                LOG.error(error)
                if ignore_error:
                    return "ERROR: " + error
                else:
                    sys.exit(1)

    for postprocess in used.get("postprocess", []):
        ignore_error = postprocess.get("ignore_error", False)

        postprocess_action = PostprocessAction(postprocess)

        for var_name in postprocess["vars"]:
            transform_path(new_vars, dot_split(var_name), postprocess_action)

    return new_vars


def update_vars(
    current_vars: dict[str, Any],
    new_vars: dict[str, Any],
    update_paths: set[str],
    path: Optional[str] = None,
) -> None:
    for key, value in new_vars.items():
        if "." in key:  # pragma: nocover
            LOG.warning("The key '%s' has a dot", key)
        key_path = key if path is None else f"{path}.{key}"
        if key_path in update_paths and key in current_vars:
            current_var = current_vars.get(key)
            if isinstance(value, dict) and isinstance(current_var, dict):
                update_vars(current_var, value, update_paths, key_path)
            elif isinstance(value, list) and isinstance(current_var, list):
                current_var.extend(value)
            elif value is None:
                LOG.warning("Update the path '%s' with None", key_path)
            else:  # pragma: nocover
                LOG.warning(
                    "Unable to update the path '%s', types '%s', '%s'",
                    key_path,
                    type(value),
                    type(current_var),
                )
        else:
            current_vars[key] = value
