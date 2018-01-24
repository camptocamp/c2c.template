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


class Options:
    engine = 'jinja'
    vars = None
    cache = None
    get_cache = None
    section = False
    files = None
    get_vars = []
    get_config = None
    files_builder = None


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
            '--get-config', 'config1.yaml', 'var_interpreted', 'var1', 'obj'
        ]
        main()

        with open('config1.yaml') as config:
            self.assertEquals(
                yaml.safe_load(config.read()),
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
                    'environment': []
                }
            )

    def test_gen_config_with_cache(self):
        from c2c.template import main
        sys.argv = [
            '', '--vars', 'c2c/tests/vars.yaml', '--get-cache', 'cache.yaml',
        ]
        main()

        sys.argv = [
            '', '--cache', 'cache.yaml',
            '--get-config', 'config1.yaml', 'var_interpreted', 'var1', 'obj'
        ]
        main()

        with open('config1.yaml') as config:
            self.assertEquals(
                yaml.safe_load(config.read()),
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
                    'environment': []
                }
            )

    def test_get_config_wrong(self):
        from c2c.template import main
        sys.argv = [
            '', '--vars', 'c2c/tests/vars.yaml',
            '--get-config', 'config2.yaml', 'wrong'
        ]
        with self.assertRaises(SystemExit):
            main()

    def test_path(self):
        from c2c.template import main
        sys.argv = [
            "", "--vars", "c2c/tests/path.yaml",
            "--get-config", "config3.yaml", "path"
        ]
        main()

        with open("config3.yaml") as config:
            self.assertEquals(
                yaml.safe_load(config.read()),
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
            '--get-config', 'config4.yaml', 'obj'
        ]
        main()

        with open('config4.yaml') as config:
            self.assertEquals(
                yaml.safe_load(config.read()),
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
            "--get-config", "config5.yaml", "3third"
        ]
        main()

        with open("config5.yaml") as config:
            self.assertEquals(
                yaml.safe_load(config.read()),
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
            "--get-config", "config6.yaml", "3third"
        ]
        main()

        with open("config6.yaml") as config:
            self.assertEquals(
                yaml.safe_load(config.read()),
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

    def test_loop(self):
        from c2c.template import do

        os.environ['AA'] = '11'

        opt = Options()
        opt.vars = 'c2c/tests/loop.yaml'
        opt.get_cache = 'loop.cache.yaml'

        do(opt)

        with open('loop.cache.yaml') as f:
            cache = yaml.safe_load(f.read())

        print(cache)
        self.assertEquals(cache['used_vars']['aa'], '11')
        self.assertEquals(cache['used_vars']['bb'], '11')
        self.assertEquals(cache['used_vars']['cc'], '11 11')

    def test_runtime_environment(self):
        import c2c.template
        sys.argv = [
            '', '--vars', 'c2c/tests/run-env.yaml',
            '--get-config', 'config-env.yaml', 'aa', 'bb', 'dd.ee', 'ff', 'gg', 'hh', 'ii'
        ]
        c2c.template.main()

        os.environ['AA'] = '11'
        os.environ['BB_CC'] = '22_33'
        os.environ['DD__EE'] = '44_55'
        os.environ['FF'] = '66'
        os.environ['GG'] = '77'
        os.environ['HH'] = '88'
        result = c2c.template.get_config('config-env.yaml')

        self.assertEquals(
            result,
            {
                'aa': '11',
                'bb': {'cc': '22_33'},
                'dd.ee': '44_55',
                'ff': 'ee66gg',
                'gg': [{'name': 'ee77gg'}, {'name': 'hh77ii'}],
                'hh': ['ee88gg', 'hh88ii'],
                'ii': '11 11 11',
            }
        )

    def test_runtime_environment_with_cache(self):
        import c2c.template
        sys.argv = [
            '', '--vars', 'c2c/tests/run-env.yaml',
            '--get-cache', 'cache.yaml',
        ]
        c2c.template.main()

        sys.argv = [
            '', '--cache', 'cache.yaml',
            '--get-config', 'config-env.yaml', 'aa', 'bb', 'dd.ee', 'ff', 'gg', 'hh', 'ii'
        ]
        c2c.template.main()

        os.environ['AA'] = '11'
        os.environ['BB_CC'] = '22_33'
        os.environ['DD__EE'] = '44_55'
        os.environ['FF'] = '66'
        os.environ['GG'] = '77'
        os.environ['HH'] = '88'
        result = c2c.template.get_config('config-env.yaml')

        self.assertEquals(
            result,
            {
                'aa': '11',
                'bb': {'cc': '22_33'},
                'dd.ee': '44_55',
                'ff': 'ee66gg',
                'gg': [{'name': 'ee77gg'}, {'name': 'hh77ii'}],
                'hh': ['ee88gg', 'hh88ii'],
                'ii': '11 11 11',
            }
        )
