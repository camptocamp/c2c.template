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


import sys
import yaml
from unittest import TestCase
from StringIO import StringIO


class TestTemplate(TestCase):

    def test_jinja(self):
        from c2c.template import main
        sys.argv = [
            '', '--engine', 'jinja', '--vars', 'c2c/tests/vars.yaml',
            '--files', 'c2c/tests/jinja.jinja'
        ]
        main()

        self.assertEquals(
            open('c2c/tests/jinja', 'r').read(),
            'var1: first, var2: second\n'
            'var3: first, second, third\n'
            'var_interpreted: 4\n'
            'JSON kernel: Linux\n'
            'YAML kernel: Linux\n'
            'pi: 3.14\n'
        )

    def test_mako(self):
        from c2c.template import main
        sys.argv = [
            '', '--engine', 'mako', '--vars', 'c2c/tests/vars.yaml',
            '--files', 'c2c/tests/mako.mako'
        ]
        main()

        self.assertEquals(
            open('c2c/tests/mako', 'r').read(),
            'var1: first, var2: second\n'
            'var3: first, second, third\n'
            'var_interpreted: 4\n'
        )

    def test_template(self):
        from c2c.template import main
        sys.argv = [
            '', '--engine', 'template', '--vars', 'c2c/tests/vars.yaml',
            '--files', 'c2c/tests/template.in'
        ]
        main()

        self.assertEquals(
            open('c2c/tests/template', 'r').read(),
            'var1: first, var2: second\n'
            'var3: first, second, third\n'
            'var_interpreted: 4\n'
        )

    def test_get_var(self):
        from c2c.template import main
        sys.argv = [
            '', '--vars', 'c2c/tests/vars.yaml', '--get-var', 'var_interpreted', 'VAR_1=var1'
        ]
        sys.stdout = StringIO()
        main()
        self.assertEquals(
            sys.stdout.getvalue(),
            "VAR_INTERPRETED=4\n"
            "VAR_1='first'\n"
        )
        sys.stdout = sys.__stdout__

    def test_get_config(self):
        from c2c.template import main
        sys.argv = [
            '', '--vars', 'c2c/tests/vars.yaml',
            '--get-config', 'config.yaml', 'var_interpreted', 'var1', 'obj'
        ]
        main()

        with open('config.yaml') as config:
            self.assertEquals(
                yaml.load(config.read()),
                {
                    'var_interpreted': 4,
                    'var1': 'first',
                    'obj': {
                        'v1': 1,
                        'v2': '2',
                        'v3': [1, 2, 3]
                    }
                }
            )

    def test_path(self):
        from c2c.template import main
        sys.argv = [
            "", "--vars", "c2c/tests/path.yaml",
            "--get-config", "config.yaml", "path"
        ]
        main()

        with open("config.yaml") as config:
            self.assertEquals(
                yaml.load(config.read()),
                {
                    "path": {
                        "var_interpreted": 4,
                        "facter_json": {"osfamily": "Debian"},
                        "facter_yaml": {"osfamily": "Debian"},
                        "pi": "3.14\n"
                    }
                }
            )

    def test_builder(self):
        from c2c.template import main
        sys.argv = [
            '', '--vars', 'c2c/tests/builder_vars.yaml',
            '--files-builder', 'c2c/tests/builder.jinja', '{name}.txt', 'iter'
        ]
        main()

        with open('aa.txt') as test:
            self.assertEquals(
                test.read(),
                "var1: first\nvar2: second"
            )

        with open('bb.txt') as test:
            self.assertEquals(
                test.read(),
                "var1: first\nvar2: 2"
            )

    def test_update(self):
        from c2c.template import main
        sys.argv = [
            '', '--vars', 'c2c/tests/update.yaml',
            '--get-config', 'config.yaml', 'obj'
        ]
        main()

        with open('config.yaml') as config:
            self.assertEquals(
                yaml.load(config.read()),
                {
                    'obj': {
                        'v1': 1,
                        'v2': 5,
                        'v3': [1, 2, 3, 3, 4, 5]
                    }
                }
            )

    def test_recursive(self):
        from c2c.template import main
        sys.argv = [
            "", "--vars", "c2c/tests/recursive.yaml",
            "--get-config", "config.yaml", "3third"
        ]
        main()

        with open("config.yaml") as config:
            self.assertEquals(
                yaml.load(config.read()),
                {
                    "3third": "wanted"
                }
            )

    def test_recursiveint(self):
        from c2c.template import main
        sys.argv = [
            "", "--vars", "c2c/tests/recursive_int.yaml",
            "--get-config", "config.yaml", "3third"
        ]
        main()

        with open("config.yaml") as config:
            self.assertEquals(
                yaml.load(config.read()),
                {
                    "3third": "123"
                }
            )
