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

from yaml import load
from argparse import ArgumentParser
from z3c.recipe.filetemplate import Template


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
        'files', nargs='*',
        help="the files to interprate"
    )
    options = parser.parse_args()

    used_vars = read_vars(options.vars)
    for key in used_vars.keys():
        if isinstance(used_vars[key], basestring):
            used_vars[key] = used_vars[key].format(**used_vars)

    if options.engine == 'jinja':
        from bottle import jinja2_template as engine
        bottle_template(options, used_vars, engine)

    elif options.engine == 'mako':
        from bottle import mako_template as engine
        bottle_template(options, used_vars, engine)

    elif options.engine == 'template':
        for template in options.files:
            c2c_template = C2cTemplate(
                template,
                template,
                used_vars
            )
            c2c_template.section = options.section
            processed = c2c_template.substitute()
            save(template, processed)


class C2cTemplate(Template):
    def _get(self, section, option, start):
        if self.section and section is not None:
            return self.recipe[section][option]  # pragma: nocover
        else:
            return self.recipe[option]


def bottle_template(options, used_vars, engine):
    for template in options.files:
        processed = engine(
            template, **used_vars
        )
        save(template, processed)


def save(template, processed):
    destination = '.'.join(template.split('.')[:-1])
    file_open = open(destination, 'wt')
    file_open.write(processed)
    file_open.close()
    os.chmod(destination, os.stat(template).st_mode)


def read_vars(vars_file):
    file_open = open(vars_file, 'r')
    used = load(file_open.read())
    file_open.close()

    curent_vars = {}
    if 'extends' in used:
        curent_vars = read_vars(used['extends'])

    new_vars = used['vars']

    if 'interpreted-vars' in used:
        globs = {'__builtins__': __builtins__, 'os': os, 'sys': sys}
        for key in used['interpreted-vars']:
            try:
                expression = new_vars[key]
            except KeyError:  # pragma: nocover
                print "ERROR: Expression for key not found: %s" % key
            try:
                evaluated = eval(expression, globs)
            except:  # pragma: nocover
                print "ERROR when evaluating %r expression %r:\n%s" % (
                    key, expression, traceback.format_exc()
                )

            new_vars[key] = evaluated

    curent_vars.update(new_vars)
    return curent_vars
