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
import yaml
from six import StringIO
from unittest import TestCase
from nose.plugins.attrib import attr


class TestTemplate(TestCase):

    maxDiff = None

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
            'pi: 3.14'
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

    @attr(template=True)
    def test_template(self):
        from c2c.template import main
        sys.argv = [
            '', '--engine', 'template', '--vars', 'c2c/tests/vars.yaml',
            '--files', 'c2c/tests/template.in'
        ]
        main()

        self.assertEquals(
            open('c2c/tests/template', 'r').read(),
            'var1: first, var2: second'
            'var3: first, second, third'
            'var_interpreted: 4'
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

    def test_gen_config(self):
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
                    'vars': {
                        'var_interpreted': 4,
                        'var1': 'first',
                        'obj': {
                            'v1': 1,
                            'v2': '2',
                            'v3': [1, 2, 3]
                        }
                    },
                    'environment': ['aa', 'bb.cc', 'dd\.ee']
                }
            )

    def test_get_config_wrong(self):
        from c2c.template import main
        sys.argv = [
            '', '--vars', 'c2c/tests/vars.yaml',
            '--get-config', 'config.yaml', 'wrong'
        ]
        with self.assertRaises(SystemExit):
            main()

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
                    "vars": {
                        "path": {
                            "var_interpreted": 4,
                            "facter_json": {"osfamily": "Debian"},
                            "facter_yaml": {"osfamily": "Debian"},
                            "pi": "3.14"
                        }
                    },
                    'environment': []
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
                    'vars': {
                        'obj': {
                            'v1': 1,
                            'v2': 5,
                            'v3': [1, 2, 3, 3, 4, 5]
                        }
                    },
                    'environment': []
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
                    'vars': {
                        "3third": "wanted"
                    },
                    'environment': []
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
                    'vars': {
                        "3third": "123"
                    },
                    'environment': []
                }
            )

    def test_get_config(self):
        from c2c.template import get_config

        os.environ['AA'] = '11'
        os.environ['BB_CC'] = '22_33'
        os.environ['DD_EE'] = '44_55'

        config = get_config('c2c/tests/config.yaml')

        self.assertEquals(config['aa'], '11')
        self.assertEquals(config['bb']['cc'], '22_33')
        self.assertEquals(config['dd.ee'], '44_55')
