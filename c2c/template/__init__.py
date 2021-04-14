# -*- coding: utf-8 -*-

# Copyright (c) 2011-2018, Camptocamp SA
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


import copy
import itertools
import json
import logging
import os
import re
import sys
import traceback
from argparse import ArgumentParser
from string import Formatter
from subprocess import CalledProcessError

import yaml
from yaml.parser import ParserError
from yamlinclude import YamlIncludeConstructor

try:
    from subprocess import check_output
except ImportError:  # pragma: nocover
    from subprocess import PIPE, Popen

    def check_output(cmd, cwd=None, stdin=None, stderr=None, shell=False):  # noqa
        """Backwards compatible check_output"""
        p = Popen(cmd, cwd=cwd, stdin=stdin, stderr=stderr, shell=shell, stdout=PIPE)
        out, _ = p.communicate()
        return out


LOG = logging.getLogger(__name__)
DOT_SPLITTER_RE = re.compile(r"(?<!\\)\.")
ESCAPE_DOT_RE = re.compile(r"\\.")
INDEX_RE = re.compile(r"^\[([0-9]+)\]$")


def dot_split(string):
    result = DOT_SPLITTER_RE.split(string)
    return [ESCAPE_DOT_RE.sub(".", i) for i in result if i != ""]


def transform_path(value, path, action, current_path=""):
    assert len(path) > 0
    key = path[0]
    if isinstance(value, list) and key == "[]":
        if len(path) == 1:
            for i, v in enumerate(value):
                value[i] = action(v, f"{current_path}[{i}]")
        else:
            for i, v in enumerate(value):
                transform_path(v, path[1:], action, f"{current_path}[{i}]")
    else:
        if isinstance(value, dict):
            if key not in value:
                LOG.warn(
                    "The key '%s' in '%s' is not present in: [%s]",
                    key,
                    current_path,
                    ", ".join(["'{}'".format(k) for k in value.keys()]),
                )
            else:
                if len(path) == 1:
                    value[key] = action(value[key], f"{current_path}.{path[0]}")
                else:
                    transform_path(value[key], path[1:], action, f"{current_path}.{path[0]}")

        elif isinstance(value, list):

            def replace(path, current_path, value, index):
                if index >= len(value):
                    LOG.warn(
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
                LOG.warn("The key '%s' in '%s' is not valid for list", key, current_path)
        else:
            LOG.warn(
                "The value '%s' in '%s' is not valid, it should be a list or a dict", value, current_path
            )


def get_config(file_name):
    with open(file_name) as f:
        config = yaml.safe_load(f.read())
    format_walker = FormatWalker(
        config["vars"], config.get("no_interpreted", []), config.get("environment", [])
    )
    format_walker()
    return do_process(config, format_walker.used_vars)


def main():
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
        used_vars,
        no_interpreted,
        environment,
        runtime_environment=None,
        runtime_environment_pattern=None,
    ):
        self.formatted = []
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

    def path_in(self, path_list, list):
        for path in path_list:
            if path in list:
                return True
        return False

    def format_walker(self, current_vars, path=None, path_list=None):
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
                        and attr not in self.all_environment_dict.keys()
                    ):
                        return current_vars, [[path, attr]]
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
                for pl in path_list:
                    new_path_list += [f"{path}[{index}]", f"{path}[]"]
                formatteds.append(self.format_walker(var, new_path, new_path_list))
            return [v for v, s in formatteds], list(itertools.chain(*[s for v, s in formatteds]))

        elif isinstance(current_vars, dict):
            skip = []
            for key in current_vars.keys():
                if path is None:
                    current_path = key
                    current_path_list = [key]
                else:
                    current_path = f"{path}.{key}"
                    current_path_list = [f"{pl}.{key}" for pl in path_list]
                current_formatted = self.format_walker(current_vars[key], current_path, current_path_list)
                current_vars[key] = current_formatted[0]
                skip += current_formatted[1]
            return current_vars, skip
        else:
            self.formatted.append(path)

        return current_vars, []

    def __call__(self):
        skip = None
        old_skip = sys.maxsize
        while skip is None or old_skip != len(skip) and len(skip) != 0:
            old_skip = sys.maxsize if skip is None else len(skip)
            self.used_vars, skip = self.format_walker(self.used_vars)

        if len(skip) > 0:
            LOG.error(
                "The following variable isn't correctly interpreted due missing dependency:\n%s",
                "\n".join(["'{}' depend on '{}'".format(*e) for e in skip]),
            )
            sys.exit(1)


def do(options):
    if options.cache is not None and options.vars is not None:
        LOG.error("The --vars and --cache options cannot be used together")
        sys.exit(1)
    if options.cache is None and options.vars is None:
        LOG.error("One of the --vars or --cache options is required")
        sys.exit(1)

    if options.cache is not None:
        with open(options.cache, "r") as file_open:
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
            "{{{}}}"
            if options.get_config is not None or options.get_cache is not None
            else options.runtime_environment_pattern,
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
            LOG.error("The get variable '{}' has more than one '='".format((get_var)))
            sys.exit(1)

        print("{}={!r}".format(corresp[0], used_vars[corresp[1]]))

    if options.get_config is not None:
        new_vars = {"vars": {}}
        for v in options.get_config[1:]:
            var_path = v.split(".")
            value = used_vars
            for key in var_path:
                if key in value:
                    value = value[key]
                else:
                    LOG.warn("The variable '%s' don't exists", v)

            new_vars["vars"][v] = value
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
            _proceed([[template, destination]], file_vars, options)

    if options.files is not None:
        files = [(f, ".".join(f.split(".")[:-1])) for f in options.files]
        _proceed(files, used_vars, options)


def get_path(value, path):
    split_path = dot_split(path)
    parent = None
    for element in split_path:
        parent = value
        value = parent[element]
    return (parent, split_path[-1]), value


def set_path(item, value):
    parent, element = item
    parent[element] = value


def _proceed(files, used_vars, options):
    if options.engine == "jinja":
        from bottle import jinja2_template as engine

        bottle_template(files, used_vars, engine)

    elif options.engine == "mako":
        from bottle import mako_template as engine

        bottle_template(files, used_vars, engine)


def bottle_template(files, used_vars, engine):
    for template, destination in files:
        processed = engine(template, **used_vars)
        save(template, destination, processed)


def save(template, destination, processed):
    with open(destination, "wb") as file_open:
        file_open.write(processed.encode("utf-8"))
    os.chmod(destination, os.stat(template).st_mode)


class BuildLoader(yaml.SafeLoader):
    pass


def read_vars(vars_file):
    YamlIncludeConstructor.add_to_loader_class(loader_class=BuildLoader, base_dir=os.path.dirname(vars_file))
    with open(vars_file, "r") as file_open:
        used = yaml.load(file_open.read(), BuildLoader)

    used.setdefault("environment", [])
    used.setdefault("runtime_environment", [])
    used.setdefault("runtime_interpreted", {})
    used.setdefault("runtime_postprocess", [])

    current_vars = {}
    if "extends" in used:
        current_vars, config = read_vars(used["extends"])

        no_interpreted = set()
        no_interpreted.update(config.get("no_interpreted", []))
        no_interpreted.update(used.get("no_interpreted", []))
        used["no_interpreted"] = list(no_interpreted)

        environment = config["environment"]
        runtime_environment = config["runtime_environment"]
        for e in used["runtime_environment"]:
            if e in environment:
                environment.remove(e)
            runtime_environment.append(e)
        for name, interpreted in config.get("runtime_interpreted", {}).items():
            if name in used["runtime_interpreted"]:
                if interpreted is list and used["runtime_interpreted"][name] is list:
                    used["runtime_interpreted"][name] += interpreted
                else:
                    value = {"vars": []}
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
        for e in used["environment"]:
            if e in runtime_environment:
                runtime_environment.remove(e)
            environment.append(e)
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


def do_process(used, new_vars):
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

        interpreters.sort(key=lambda v: -v["priority"])

        for interpreter in interpreters:
            for var_name in interpreter["vars"]:
                if "cmd" in interpreter:
                    ignore_error = interpreter.get("ignore_error", False)

                    def action(expression, current_path):
                        cmd = interpreter["cmd"][:]  # [:] to clone
                        cmd.append(expression)
                        try:
                            with open(os.devnull, "w") as dev_null:
                                return (
                                    check_output(cmd, stderr=dev_null if ignore_error else None)
                                    .decode("utf-8")
                                    .strip("\n")
                                )
                        except (OSError, CalledProcessError) as e:  # pragma: nocover
                            error = "When running the expression '{}' in '{}': {}".format(
                                expression, current_path, e
                            )
                            LOG.error(error)
                            if ignore_error:
                                return "ERROR: " + error
                            else:
                                sys.exit(1)

                elif interpreter["name"] == "python":

                    def action(expression, current_path):
                        try:
                            return eval(expression, globs)
                        except Exception:  # pragma: nocover
                            error = "When evaluating {} expression '{}' in '{}' as Python:\n{}".format(
                                var_name, expression, current_path, traceback.format_exc()
                            )
                            LOG.error(error)
                            if interpreter.get("ignore_error", False):
                                return "ERROR: " + error
                            else:
                                sys.exit(1)

                elif interpreter["name"] == "bash":

                    def action(expression, current_path):
                        try:
                            return check_output(expression, shell=True).decode("utf-8").strip("\n")
                        except (OSError, CalledProcessError) as e:  # pragma: nocover
                            error = "When running the expression '{}' in [{}]: {}".format(
                                expression, current_path, e
                            )
                            LOG.error(error)
                            if interpreter.get("ignore_error", False):
                                return "ERROR: " + error
                            else:
                                sys.exit(1)

                elif interpreter["name"] == "json":

                    def action(value, current_path):
                        try:
                            return json.loads(value)
                        except ValueError as e:  # pragma: nocover
                            error = "When evaluating {} expression '{}' in '{}' as JSON: {}".format(
                                key, value, current_path, e
                            )
                            LOG.error(error)
                            if interpreter.get("ignore_error", False):
                                return "ERROR: " + error
                            else:
                                sys.exit(1)

                elif interpreter["name"] == "yaml":

                    def action(value, current_path):
                        try:
                            return yaml.safe_load(value)
                        except ParserError as e:  # pragma: nocover
                            error = "When evaluating {} expression '{}' in '{}' as YAML: {}".format(
                                key, value, current_path, e
                            )
                            LOG.error(error)
                            if interpreter.get("ignore_error", False):
                                return "ERROR: " + error
                            else:
                                sys.exit(1)

                else:  # pragma: nocover
                    LOG.error("Unknown interpreter name '{}'".format(interpreter["name"]))
                    sys.exit(1)

                try:
                    transform_path(new_vars, dot_split(var_name), action)
                except KeyError:  # pragma: nocover
                    LOG.error("Expression for key not found: {}".format(var_name))
                    sys.exit(1)

    for postprocess in used.get("postprocess", []):
        ignore_error = postprocess.get("ignore_error", False)

        def postprocess_action(value, current_path):
            expression = postprocess["expression"]  # [:] to clone
            expression = expression.format(repr(value))
            try:
                return eval(expression, globs)
            except ValueError as e:  # pragma: nocover
                error = "When interpreting the expression '{}' in '{}': {}".format(
                    expression, current_path, e
                )
                LOG.error(error)
                if ignore_error:
                    return "ERROR: " + error
                else:
                    sys.exit(1)

        for var_name in postprocess["vars"]:
            transform_path(new_vars, dot_split(var_name), postprocess_action)

    return new_vars


def update_vars(current_vars, new_vars, update_paths, path=None):
    for key, value in new_vars.items():
        if "." in key:  # pragma: nocover
            LOG.warn("The key '%s' has a dot", key)
        key_path = key if path is None else "{}.{}".format(path, key)
        if key_path in update_paths and key in current_vars:
            if isinstance(value, dict) and isinstance(current_vars.get(key), dict):
                update_vars(current_vars.get(key), value, update_paths, key_path)
            elif isinstance(value, list) and isinstance(current_vars.get(key), list):
                current_vars.get(key).extend(value)
            elif value is None:
                LOG.warn("Update the path '%s' with None", key_path)
            else:  # pragma: nocover
                LOG.warn(
                    "Unable to update the path '%s', types '%s', '%s'",
                    key_path,
                    type(value),
                    type(current_vars.get(key)),
                )
        else:
            current_vars[key] = value
