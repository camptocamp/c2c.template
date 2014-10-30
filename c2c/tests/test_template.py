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
from unittest import TestCase


class TestTemplate(TestCase):

    def test_jinja(self):
        from c2c.template import main
        sys.argv = ['', '--engine', 'jinja', '--vars', 'c2c/tests/vars.yaml', 'c2c/tests/jinja.jinja']
        main()

        self.AssertEquals(
            open('c2c/tests/jinja', 'r').read(),
            'var1: first, var2: second'
        )

    def test_mako(self):
        from c2c.template import main
        sys.argv = ['', '--engine', 'mako', '--vars', 'c2c/tests/vars.yaml', 'c2c/tests/mako.mako']
        main()

        self.AssertEquals(
            open('c2c/tests/mako', 'r').read(),
            'var1: first, var2: second'
        )

    def test_template(self):
        from c2c.template import main
        sys.argv = ['', '--engine', 'jinja', '--vars', 'c2c/tests/vars.yaml', 'c2c/tests/tempplate.in']
        main()

        self.AssertEquals(
            open('c2c/tests/template', 'r').read(),
            'var1: first, var2: second'
        )
