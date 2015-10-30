
Create a new release
--------------------

.. code::

    git clean -fd
    venv/bin/python setup.py egg_info --no-date --tag-build "" bdist_wheel sdist upload -r pypi
