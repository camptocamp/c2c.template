c2c.template
============

Supported template Jinja, Mako, Template.

Tools that collect some vars and get them to a template engine.

Supported template: `Jinja <http://jinja.pocoo.org/>`_,
`Mako <http://www.makotemplates.org/>`_ and
`Template https://pypi.python.org/pypi/z3c.recipe.filetemplate`_.

Use ``c2c-template --help`` to get the command line help.

Vars file
=========

The vars collector gets the vars from YAML files like this one:

.. code:: yaml

   extends: inherit.yaml

   vars:
        string_var: a string
        int_var: 42
        interpreted_var: __import__('datetime').date.today()
        combined_var: 'Today: {interpreted_var:%Y-%m-%d}'

    interpreted-vars:
    - interpreted_var

The ``inherit.yaml`` is an other file with the same syntax that will provide
initial vars.

The ``vars`` section is where we define the vars values, the YAML files
support typing, than ``42`` will be an integer.

The ``interpreted-vars`` is a list of variable that the value will be
interpreted, than the ``interpreted_var`` will have the value ``4``,
See: `eval() <https://docs.python.org/2/library/functions.html#eval>`_.

The ``combined_var`` reuse a predefined variable and format,
See: `str.format() <https://docs.python.org/2/library/string.html#formatstrings>`_.
