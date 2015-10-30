# -*- coding: utf-8 -*-

# Copyright (c) 2011-2014, Camptocamp SA
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


import os
import sys
import traceback
import json
import yaml
from yaml.parser import ParserError
from argparse import ArgumentParser
from string import Formatter
from z3c.recipe.filetemplate import Template
from subprocess import CalledProcessError
try:
    from subprocess import check_output
except ImportError:  # pragma: nocover
    from subprocess import Popen, PIPE

    def check_output(cmd, cwd=None, stdin=None, stderr=None, shell=False):  # noqa
        """Backwards compatible check_output"""
        p = Popen(cmd, cwd=cwd, stdin=stdin, stderr=stderr, shell=shell, stdout=PIPE)
        out, err = p.communicate()
        return out


def main():
    parser = ArgumentParser(
        description='Used to run a template'
    )
    parser.add_argument(
        '--engine', '-e', choices=['jinja', 'mako', 'template'], default='jinja',
        help='the used template engine'
    )
    parser.add_argument(
        '--vars', '-c', default='vars.yaml',
        help="the YAML file defining the variables"
    )
    parser.add_argument(
        '--section', action='store_true',
        help="use the section (template specific)"
    )
    parser.add_argument(
        '--files', nargs='*',
        help="the files to interpret"
    )
    parser.add_argument(
        '--get-vars', nargs='*', default=[],
        help="the vars to get, can be MY_VAR=my_var"
    )
    parser.add_argument(
        '--get-config', nargs='*',
        help="generate a configuration file"
    )
    files_builder_help = \
        "generate some files from a source file (first ARG), " \
        "to files (second ARG, with format we can access to the value attribute), " \
        "and get the value on iter on the variable referenced by the third argument"
    parser.add_argument(
        '--files-builder', nargs=3,
        metavar='ARG', help=files_builder_help
    )
    options = parser.parse_args()

    used_vars = read_vars(options.vars)

    formatter = Formatter()
    formatted = []

    def format_walker(current_vars, path=None):
        if isinstance(current_vars, basestring):
            if path not in formatted:
                attrs = formatter.parse(current_vars)
                for _, attr, _, _ in attrs:
                    if attr is not None and attr not in formatted:
                        return current_vars, 1
                formatted.append(path)
                return current_vars.format(**used_vars), 0
            return current_vars, 0

        elif isinstance(current_vars, list):
            formatteds = [
                format_walker(var, "%s[%i]" % (path, index))
                for index, var in enumerate(current_vars)
            ]
            return [v for v, s in formatteds], sum([s for v, s in formatteds])

        elif isinstance(current_vars, dict):
            skip = 0
            for key in current_vars.keys():
                if path is None:
                    current_path = key
                else:
                    current_path = "%s[%s]" % (path, key)
                current_formatted = format_walker(current_vars[key], current_path)
                current_vars[key] = current_formatted[0]
                skip += current_formatted[1]
            return current_vars, skip
        else:
            formatted.append(path)

        return current_vars, 0
    old_skip = 0
    skip = -1
    while old_skip != skip and skip != 0:
        old_skip = skip
        used_vars, skip = format_walker(used_vars)

    for get_var in options.get_vars:
        corresp = get_var.split('=')
        if len(corresp) == 1:
            corresp = (get_var.upper(), get_var)

        if len(corresp) != 2:  # pragma: nocover
            print("ERROR the get variable '%s' has more than one '='." % (
                get_var
            ))
            exit(1)

        print("%s=%r" % (corresp[0], used_vars[corresp[1]]))

    if options.get_config is not None:
        new_vars = {}
        for v in options.get_config[1:]:
            var_path = v.split('.')
            value = used_vars
            for key in var_path:
                if key in value:
                    value = value[key]
                else:
                    print("ERROR the variable '%s' don't exists." % v)
                    exit(1)

            new_vars[v] = value

        with open(options.get_config[0], 'wb') as file_open:
            file_open.write(yaml.dump(new_vars))

    if options.files_builder is not None:
        var_path = options.files_builder[2].split('.')
        values = used_vars
        for key in var_path:
            values = values[key]

        if not isinstance(values, list):  # pragma: nocover
            print("ERROR the variable '%s': '%r' should be an array." % (
                options.files_builder[2], values
            ))

        for value in values:
            file_vars = {}
            file_vars.update(used_vars)
            file_vars.update(value)
            template = options.files_builder[0]
            destination = options.files_builder[1].format(**value)
            _proceed([[template, destination]], file_vars, options)

    if options.files is not None:
        files = [(f, '.'.join(f.split('.')[:-1])) for f in options.files]
        _proceed(files, used_vars, options)


def get_path(value, path):
    split_path = path.split(".")
    parent = None
    for element in split_path:
        parent = value
        value = parent[element]
    return (parent, split_path[-1]), value


def set_path(item, value):
    parent, element = item
    parent[element] = value


def _proceed(files, used_vars, options):
    if options.engine == 'jinja':
        from bottle import jinja2_template as engine
        bottle_template(files, used_vars, engine)

    elif options.engine == 'mako':
        from bottle import mako_template as engine
        bottle_template(files, used_vars, engine)

    elif options.engine == 'template':
        for template, destination in files:
            c2c_template = C2cTemplate(
                template,
                template,
                used_vars
            )
            c2c_template.section = options.section
            processed = unicode(c2c_template.substitute(), "utf8")
            save(template, destination, processed)


class C2cTemplate(Template):
    def _get(self, section, option, start):
        if self.section and section is not None:
            return self.recipe[section][option]  # pragma: nocover
        else:
            return self.recipe[option]


def bottle_template(files, used_vars, engine):
    for template, destination in files:
        processed = engine(
            template, **used_vars
        )
        save(template, destination, processed)


def save(template, destination, processed):
    with open(destination, 'wb') as file_open:
        file_open.write(processed.encode("utf-8"))
    os.chmod(destination, os.stat(template).st_mode)


def read_vars(vars_file):
    with open(vars_file, 'r') as file_open:
        used = yaml.load(file_open.read())

    current_vars = {}
    if 'extends' in used:
        current_vars = read_vars(used['extends'])

    new_vars = used['vars']

    if 'interpreted' in used:
        interpreters = []
        globs = {'__builtins__': __builtins__, 'os': os, 'sys': sys}
        for key, interpreter in used['interpreted'].items():
            if isinstance(interpreter, dict):
                interpreter["name"] = key
                if 'priority' not in interpreter:
                    interpreter["priority"] = 0 if key in ['json', 'yaml'] else 100
            else:
                interpreter = {
                    "name": key,
                    "vars": interpreter,
                    "priority": 0 if key in ['json', 'yaml'] else 100
                }
            interpreters.append(interpreter)

        interpreters.sort(key=lambda v: -v["priority"])

        for interpreter in interpreters:
            for var_name in interpreter["vars"]:
                try:
                    item, expression = get_path(new_vars, var_name)
                except KeyError:  # pragma: nocover
                    print("ERROR: Expression for key not found: %s" % var_name)
                    exit(1)

                if "cmd" in interpreter:
                    cmd = interpreter["cmd"][:]  # [:] to clone
                    cmd.append(expression)
                    try:
                        evaluated = check_output(cmd)
                    except OSError as e:  # pragma: nocover
                        print("ERROR when running the expression '%r': %s" % (
                            expression, e
                        ))
                        exit(1)
                    except CalledProcessError as e:  # pragma: nocover
                        error = "ERROR when running the expression '%r': %s" % (
                            expression, e
                        )
                        print(error)
                        if interpreter.get("ignore_error", False):
                            evaluated = error
                        else:
                            exit(1)

                elif interpreter["name"] == "python":
                    try:
                        evaluated = eval(expression, globs)
                    except:  # pragma: nocover
                        error = "ERROR when evaluating %r expression %r as Python:\n%s" % (
                            var_name, expression, traceback.format_exc()
                        )
                        print(error)
                        if interpreter.get("ignore_error", False):
                            evaluated = error
                        else:
                            exit(1)
                elif interpreter["name"] == 'bash':
                    try:
                        evaluated = check_output(expression, shell=True)
                    except OSError as e:  # pragma: nocover
                        print("ERROR when running the expression '%r': %s" % (
                            expression, e
                        ))
                        exit(1)
                    except CalledProcessError as e:  # pragma: nocover
                        error = "ERROR when running the expression '%r': %s" % (
                            expression, e
                        )
                        print(error)
                        if interpreter.get("ignore_error", False):
                            evaluated = error
                        else:
                            exit(1)

                elif interpreter["name"] == 'environment':  # pragma: nocover
                    if expression is None:
                        evaluated = os.environ
                    else:
                        try:
                            evaluated = os.environ[expression]
                        except KeyError:
                            error = \
                                "ERROR when getting %r in environment variables, " \
                                "possible values are: %r" % (
                                    expression, os.environ.keys()
                                )
                            print(error)
                            if interpreter.get("ignore_error", False):
                                evaluated = error
                            else:
                                exit(1)
                elif interpreter["name"] == 'json':
                    try:
                        evaluated = json.loads(expression)
                    except ValueError as e:  # pragma: nocover
                        error = "ERROR when evaluating %r expression %r as JSON: %s" % (
                            key, expression, e
                        )
                        print(error)
                        if interpreter.get("ignore_error", False):
                            evaluated = error
                        else:
                            exit(1)
                elif interpreter["name"] == 'yaml':
                    try:
                        evaluated = yaml.load(expression)
                    except ParserError as e:  # pragma: nocover
                        error = "ERROR when evaluating %r expression %r as YAML: %s" % (
                            key, expression, e
                        )
                        print(error)
                        if interpreter.get("ignore_error", False):
                            evaluated = error
                        else:
                            exit(1)
                else:  # pragma: nocover
                    print("Unknown interpreter name '{}'.".format(interpreter["name"]))
                    exit(1)

                set_path(item, evaluated)

    update_paths = []
    for update_path in used.get("update_paths", []):
        split_path = update_path.split(".")
        for i in range(len(split_path)):
            update_paths.append(".".join(split_path[:i + 1]))
    update_vars(current_vars, new_vars, set(update_paths))
    return current_vars


def update_vars(current_vars, new_vars, update_paths, path=None):
    for key, value in new_vars.items():
        if "." in key:  # pragma: nocover
            print("WARNING: the key '%s' has a dot" % key)
        key_path = key if path is None else "%s.%s" % (path, key)
        if key_path in update_paths:
            if isinstance(value, dict) and isinstance(current_vars.get(key), dict):
                update_vars(current_vars.get(key), value, update_paths, key_path)
            elif isinstance(value, list) and isinstance(current_vars.get(key), list):
                current_vars.get(key).extend(value)
            else:  # pragma: nocover
                print("ERROR: Unable to update the path '%s', types '%r', '%r'." % (
                    key_path, type(value), type(current_vars.get(key))
                ))
        else:
            current_vars[key] = value
