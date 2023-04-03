# Copyright (c) 2011-2023, Camptocamp SA
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


import json
import os
import sys
from io import StringIO
from unittest import TestCase

import yaml


class Options:
    engine = "jinja"
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
            "",
            "--engine",
            "jinja",
            "--vars",
            "c2c/tests/vars.yaml",
            "--files",
            "c2c/tests/jinja.jinja",
        ]
        main()

        self.assertEqual(
            open("c2c/tests/jinja").read(),
            "var1: first, var2: second\n"
            "var3: first, second, third\n"
            "var_interpreted: 4\n"
            "JSON kernel: Linux\n"
            "YAML kernel: Linux\n"
            "pi: 3.14",
        )

    def test_mako(self):
        from c2c.template import main

        sys.argv = ["", "--engine", "mako", "--vars", "c2c/tests/vars.yaml", "--files", "c2c/tests/mako.mako"]
        main()

        self.assertEqual(
            open("c2c/tests/mako").read(),
            "var1: first, var2: second\n" "var3: first, second, third\n" "var_interpreted: 4\n",
        )

    def test_get_var(self):
        from c2c.template import main

        sys.argv = ["", "--vars", "c2c/tests/vars.yaml", "--get-var", "var_interpreted", "VAR_1=var1"]
        sys.stdout = StringIO()
        main()
        self.assertEqual(sys.stdout.getvalue(), "VAR_INTERPRETED=4\n" "VAR_1='first'\n")
        sys.stdout = sys.__stdout__

    def test_gen_config(self):
        from c2c.template import main

        sys.argv = [
            "",
            "--vars",
            "c2c/tests/vars.yaml",
            "--get-config",
            "config1.yaml",
            "var_interpreted",
            "var1",
            "obj",
        ]
        main()

        with open("config1.yaml") as config:
            self.assertEqual(
                yaml.safe_load(config.read()),
                {
                    "vars": {
                        "var_interpreted": 4,
                        "var1": "first",
                        "obj": {"v1": 1, "v2": "2", "v3": [1, 2, 3]},
                    },
                    "environment": [],
                    "interpreted": {},
                    "no_interpreted": [],
                    "postprocess": [],
                },
            )

    def test_gen_config_with_cache(self):
        from c2c.template import main

        sys.argv = [
            "",
            "--vars",
            "c2c/tests/vars.yaml",
            "--get-cache",
            "cache.yaml",
        ]
        main()

        sys.argv = [
            "",
            "--cache",
            "cache.yaml",
            "--get-config",
            "config1.yaml",
            "var_interpreted",
            "var1",
            "obj",
        ]
        main()

        with open("config1.yaml") as config:
            self.assertEqual(
                yaml.safe_load(config.read()),
                {
                    "vars": {
                        "var_interpreted": 4,
                        "var1": "first",
                        "obj": {"v1": 1, "v2": "2", "v3": [1, 2, 3]},
                    },
                    "environment": [],
                    "interpreted": {},
                    "no_interpreted": [],
                    "postprocess": [],
                },
            )

    def test_path(self):
        from c2c.template import main

        sys.argv = ["", "--vars", "c2c/tests/path.yaml", "--get-config", "config3.yaml", "path"]
        main()

        with open("config3.yaml") as config:
            self.assertEqual(
                yaml.safe_load(config.read()),
                {
                    "vars": {
                        "path": {
                            "var_interpreted": 4,
                            "facter_json": {"osfamily": "Debian"},
                            "facter_yaml": {"osfamily": "Debian"},
                            "pi": "3.14",
                        }
                    },
                    "environment": [],
                    "interpreted": {},
                    "no_interpreted": [],
                    "postprocess": [],
                },
            )

    def test_builder(self):
        from c2c.template import main

        sys.argv = [
            "",
            "--vars",
            "c2c/tests/builder_vars.yaml",
            "--files-builder",
            "c2c/tests/builder.jinja",
            "{name}.txt",
            "iter",
        ]
        main()

        with open("aa.txt") as test:
            self.assertEqual(test.read(), "var1: first\nvar2: second")

        with open("bb.txt") as test:
            self.assertEqual(test.read(), "var1: first\nvar2: 2")

    def test_builder_dict(self):
        from c2c.template import main

        sys.argv = [
            "",
            "--vars",
            "c2c/tests/builder_vars_dict.yaml",
            "--files-builder",
            "c2c/tests/builder.jinja",
            "{name}.txt",
            "iter",
        ]
        main()

        with open("aa.txt") as test:
            self.assertEqual(test.read(), "var1: first\nvar2: second")

        with open("bb.txt") as test:
            self.assertEqual(test.read(), "var1: first\nvar2: 2")

    def test_update(self):
        from c2c.template import main

        sys.argv = ["", "--vars", "c2c/tests/update.yaml", "--get-config", "config4.yaml", "obj"]
        main()

        with open("config4.yaml") as config:
            self.assertEqual(
                yaml.safe_load(config.read()),
                {
                    "vars": {"obj": {"v1": 1, "v2": 5, "v3": [1, 2, 3, 3, 4, 5]}},
                    "environment": [],
                    "interpreted": {},
                    "no_interpreted": [],
                    "postprocess": [],
                },
            )

    def test_recursive(self):
        from c2c.template import main

        sys.argv = ["", "--vars", "c2c/tests/recursive.yaml", "--get-config", "config5.yaml", "3third"]
        main()

        with open("config5.yaml") as config:
            self.assertEqual(
                yaml.safe_load(config.read()),
                {
                    "vars": {"3third": "wanted"},
                    "environment": [],
                    "interpreted": {},
                    "no_interpreted": [],
                    "postprocess": [],
                },
            )

    def test_recursiveint(self):
        from c2c.template import main

        sys.argv = ["", "--vars", "c2c/tests/recursive_int.yaml", "--get-config", "config6.yaml", "3third"]
        main()

        with open("config6.yaml") as config:
            self.assertEqual(
                yaml.safe_load(config.read()),
                {
                    "vars": {"3third": "123"},
                    "environment": [],
                    "interpreted": {},
                    "no_interpreted": [],
                    "postprocess": [],
                },
            )

    def test_get_config(self):
        from c2c.template import get_config

        os.environ["AA"] = "11"
        os.environ["BB_CC"] = "22_33"
        os.environ["DD_EE"] = "44_55"

        config = get_config("c2c/tests/config.yaml")

        self.assertEqual(config["aa"], "11")
        self.assertEqual(config["bb"]["cc"], "22_33")
        self.assertEqual(config["dd.ee"], "44_55")

    def test_loop(self):
        from c2c.template import do

        os.environ["AA"] = "11"

        opt = Options()
        opt.vars = "c2c/tests/loop.yaml"
        opt.get_cache = "loop.cache.yaml"
        opt.runtime_environment_pattern = None

        do(opt)

        with open("loop.cache.yaml") as f:
            cache = yaml.safe_load(f.read())

        self.assertEqual(cache["used_vars"]["aa"], "11")
        self.assertEqual(cache["used_vars"]["bb"], "11")
        self.assertEqual(cache["used_vars"]["cc"], "11 11")

    def test_runtime_environment(self):
        import c2c.template

        sys.argv = [
            "",
            "--vars",
            "c2c/tests/run-env.yaml",
            "--get-config",
            "config-env.yaml",
            "aa",
            "bb",
            "dd.ee",
            "ff",
            "gg",
            "hh",
            "ii",
        ]
        c2c.template.main()

        os.environ["AA"] = "11"
        os.environ["BB_CC"] = "22_33"
        os.environ["DD__EE"] = "44_55"
        os.environ["FF"] = "66"
        os.environ["GG"] = "77"
        os.environ["HH"] = "88"
        result = c2c.template.get_config("config-env.yaml")

        self.assertEqual(
            result,
            {
                "aa": "11",
                "bb": {"cc": "22_33"},
                "dd.ee": "44_55",
                "ff": "ee66gg",
                "gg": [{"name": "ee77gg"}, {"name": "hh77ii"}],
                "hh": ["ee88gg", "hh88ii"],
                "ii": "11 11 11",
            },
        )

    def test_extends_runtime_environment(self):
        import c2c.template

        os.environ["AA"] = "11"
        os.environ["FF"] = "66"
        os.environ["GG"] = "77"
        os.environ["HH"] = "88"
        sys.argv = [
            "",
            "--vars",
            "c2c/tests/extends-run-env.yaml",
            "--get-config",
            "config-env.yaml",
            "aa",
            "bb",
            "dd.ee",
            "ff",
            "gg",
            "hh",
            "ii",
        ]
        c2c.template.main()
        del os.environ["AA"]
        del os.environ["FF"]
        del os.environ["GG"]
        del os.environ["HH"]

        with open("config-env.yaml") as config:
            self.assertEqual(
                yaml.safe_load(config.read()),
                {
                    "vars": {
                        "aa": "11",
                        "bb": {"cc": "{BB_CC}"},
                        "dd.ee": "66_77",
                        "ff": "ee66gg",
                        "gg": [{"name": "ee77gg"}, {"name": "hh77ii"}],
                        "hh": ["ee88gg", "hh88ii"],
                        "ii": "11 11 11",
                    },
                    "environment": [{"name": "BB_CC"}, {"name": "DD_EE", "default": "44_55"}],
                    "interpreted": {},
                    "no_interpreted": [],
                    "postprocess": [],
                },
            )

        os.environ["BB_CC"] = "22_33"
        result = c2c.template.get_config("config-env.yaml")

        self.assertEqual(
            result,
            {
                "aa": "11",
                "bb": {"cc": "22_33"},
                "dd.ee": "66_77",
                "ff": "ee66gg",
                "gg": [{"name": "ee77gg"}, {"name": "hh77ii"}],
                "hh": ["ee88gg", "hh88ii"],
                "ii": "11 11 11",
            },
        )

    def test_runtime_environment_with_cache(self):
        import c2c.template

        sys.argv = [
            "",
            "--vars",
            "c2c/tests/run-env.yaml",
            "--get-cache",
            "cache.yaml",
        ]
        c2c.template.main()

        sys.argv = [
            "",
            "--cache",
            "cache.yaml",
            "--get-config",
            "config-env.yaml",
            "aa",
            "bb",
            "dd.ee",
            "ff",
            "gg",
            "hh",
            "ii",
        ]
        c2c.template.main()

        os.environ["AA"] = "11"
        os.environ["BB_CC"] = "22_33"
        os.environ["DD_EE"] = "44_66"
        os.environ["FF"] = "66"
        os.environ["GG"] = "77"
        os.environ["HH"] = "88"
        result = c2c.template.get_config("config-env.yaml")

        self.assertEqual(
            result,
            {
                "aa": "11",
                "bb": {"cc": "22_33"},
                "dd.ee": "44_66",
                "ff": "ee66gg",
                "gg": [{"name": "ee77gg"}, {"name": "hh77ii"}],
                "hh": ["ee88gg", "hh88ii"],
                "ii": "11 11 11",
            },
        )

    def test_no_interpreted(self):
        import c2c.template

        sys.argv = [
            "",
            "--vars",
            "c2c/tests/no_interpreted.yaml",
            "--get-cache",
            "cache.yaml",
        ]
        c2c.template.main()

        sys.argv = ["", "--cache", "cache.yaml", "--get-config", "config.yaml", "var"]
        c2c.template.main()

        result = c2c.template.get_config("config.yaml")

        self.assertEqual(
            result,
            {
                "var": "{test}",
            },
        )

    def test_runtime_postprocess(self):
        import c2c.template

        sys.argv = [
            "",
            "--vars",
            "c2c/tests/postprocess.yaml",
            "--get-config",
            "config.yaml",
            "a",
            "b",
            "c.d",
            "e",
            "f",
            "g",
            "h",
            "i",
        ]
        c2c.template.main()

        os.environ["A"] = "11"
        os.environ["B"] = '{"name": "toto"}'
        result = c2c.template.get_config("config.yaml")

        self.assertEqual(
            result,
            {
                "a": 11,
                "b": {"name": "toto"},
                "c.d": 3,
                "e": "{C}",
                "f": ["{D}"],
                "g": ["{E}"],
                "h": [1],
                "i": [2],
            },
        )

    def test_template_missing_runtime_environment(self):
        import c2c.template

        sys.argv = [
            "",
            "--vars",
            "c2c/tests/run-env.yaml",
            "--engine",
            "mako",
            "--files",
            "c2c/tests/env.tmpl.mako",
        ]
        self.assertRaises(SystemExit, c2c.template.main)

    def test_template_runtime_environment(self):
        import c2c.template

        sys.argv = [
            "",
            "--vars",
            "c2c/tests/run-env.yaml",
            "--engine",
            "mako",
            "--runtime-environment-pattern=${{{}}}",
            "--files",
            "c2c/tests/env.tmpl.mako",
        ]
        c2c.template.main()

        self.assertEqual(open("c2c/tests/env.tmpl").read(), "${AA}\n")

    def test_template_missing_runtime_environment_cache(self):
        import c2c.template

        sys.argv = [
            "",
            "--vars",
            "c2c/tests/run-env.yaml",
            "--get-cache",
            "cache.yaml",
        ]
        c2c.template.main()

        sys.argv = [
            "",
            "--cache",
            "cache.yaml",
            "--engine",
            "mako",
            "--files",
            "c2c/tests/env.tmpl.mako",
        ]
        self.assertRaises(SystemExit, c2c.template.main)

    def test_template_runtime_environment_cache(self):
        import c2c.template

        sys.argv = [
            "",
            "--vars",
            "c2c/tests/run-env.yaml",
            "--get-cache",
            "cache.yaml",
        ]
        c2c.template.main()

        sys.argv = [
            "",
            "--cache",
            "cache.yaml",
            "--engine",
            "mako",
            "--runtime-environment-pattern=${{{}}}",
            "--files",
            "c2c/tests/env.tmpl.mako",
        ]
        c2c.template.main()

        self.assertEqual(open("c2c/tests/env.tmpl").read(), "${AA}\n")

    def test_include_cache(self):
        import c2c.template

        sys.argv = [
            "",
            "--vars",
            "c2c/tests/include.yaml",
            "--get-cache",
            "cache.json",
        ]
        c2c.template.main()

        self.assertEqual(
            json.loads(open("cache.json").read()),
            {
                "used_vars": {"ggg": {"a": {"c": "g"}}, "hhh": [1, 2], "iii": [{"a": {"c": "g"}}]},
                "config": {"runtime_environment": [], "runtime_interpreted": {}, "runtime_postprocess": []},
            },
        )
