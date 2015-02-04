c2c.template
============

Supported template Jinja, Mako, Template.

Tools that collect some vars and get them to a template engine.

Supported template: `Jinja <http://jinja.pocoo.org/>`_,
`Mako <http://www.makotemplates.org/>`_ and
`Template <https://pypi.python.org/pypi/z3c.recipe.filetemplate>`_.

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
        facter_json: /usr/bin/facter --json
        facter_yaml: /usr/bin/facter --yaml
        pi: console.log(Math.PI.toPrecision(3))
        obj:
            v1: 1
            v2: '2'
            v3: [1, 2, 3]

    interpreted:
        python:
        - interpreted_var
        bash:
        - facter_json
        - facter_yaml
        json:
        - facter_json
        yaml:
        - facter_yaml
        node:
            vars: ["pi"]
            cmd: ["node", "-e"]

    update_path:
    - obj

The ``inherit.yaml`` is an other file with the same syntax that will provide
initial vars.

The ``vars`` section is where we define the vars values, the YAML files
support typing, than ``42`` will be an integer.

The ``interpreted`` configuration to interpret some vars,
``python``, ``bash``, ``environ``, ``json``, ``yaml`` are predefined
interpreter, ``node`` is a custom interpreter.

The ``update_path`` is a list of '.'-separated paths that will be updated (for dicts)
or appended (for lists), instead of overwritten. The sub path will be implicitly added.

We can reuse predefined variables and format them (see ``combined_var``),
See: `str.format() <https://docs.python.org/2/library/string.html#formatstrings>`_.


Example of usage
================


Interpret variable in a template
--------------------------------

.. code:: bash

    c2c-template --vars vars.yaml --engine jinja --files template.jinja

The result will be stored in a file named ``template``.


Get the vars
------------

It can be useful to get the variable outside.

.. code:: bash

    `c2c-template --vars vars.yaml --get-vars INT_VAR=int_var string_var`

That will set the bash variable ``INT_VAR`` to 42, and ``STRING_VAR`` to 'a string'.


Get a configuration file
------------------------

.. code:: bash

    c2c-template --vars vars.yaml --get-config config.yaml string-var int-var combined-var

Will create a file named ``config.yaml`` this:

.. code:: yaml

   string-var: a string
   int-var: 42
   combined-var: Today: 2014-12-12


Build a set of file based on a template
---------------------------------------

Create the following vars file (``vars.yaml``):

.. code:: yaml

    vars:
        var1: common
        iter:
        - name: one
          var2: first
        - name: two
          var2: second

And the following template (``template.jinja``):

.. code::

   var1: {{ var1 }}
   var2: {{ var2 }}

And run the following command:

.. code:: bash

    c2c-template --vars vars.yaml --files-builder template.jinja {name}.txt iter

This will create two files:

the ``one.txt`` file, with::

    var1: common
    var2: first

The ``two.txt`` file, with::

    var1: common
    var2: second
