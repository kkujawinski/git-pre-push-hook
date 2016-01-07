========
Overview
========

.. start-badges

.. list-table::
    :stub-columns: 1

    * - tests
      - | |travis|
        | |codecov|
        |
    * - package
      - |version| |downloads| |wheel| |supported-versions| |supported-implementations|

.. |travis| image:: https://travis-ci.org/kkujawinski/git-pre-push-hook.svg?branch=master
    :alt: Travis-CI Build Status
    :target: https://travis-ci.org/kkujawinski/git-pre-push-hook

.. |codecov| image:: https://codecov.io/github/kkujawinski/git-pre-push-hook/coverage.svg?branch=master
    :alt: Coverage Status
    :target: https://codecov.io/github/kkujawinski/git-pre-push-hook

.. |version| image:: https://img.shields.io/pypi/v/git-pre-push-hook.svg?style=flat
    :alt: PyPI Package latest release
    :target: https://pypi.python.org/pypi/git-pre-push-hook

.. |downloads| image:: https://img.shields.io/pypi/dm/git-pre-push-hook.svg?style=flat
    :alt: PyPI Package monthly downloads
    :target: https://pypi.python.org/pypi/git-pre-push-hook

.. |wheel| image:: https://img.shields.io/pypi/wheel/git-pre-push-hook.svg?style=flat
    :alt: PyPI Wheel
    :target: https://pypi.python.org/pypi/git-pre-push-hook

.. |supported-versions| image:: https://img.shields.io/pypi/pyversions/git-pre-push-hook.svg?style=flat
    :alt: Supported versions
    :target: https://pypi.python.org/pypi/git-pre-push-hook

.. |supported-implementations| image:: https://img.shields.io/pypi/implementation/git-pre-push-hook.svg?style=flat
    :alt: Supported implementations
    :target: https://pypi.python.org/pypi/git-pre-push-hook


.. end-badges

Pre push hook running linters.

* Free software: BSD license

Installation
============

::

    pip install git-pre-push-hook

Install hook to current Git-repository:

::

    install-git-pre-push-hook

Default pre-push hook:

::

    python -c "import pre_push_hook; sys.exit(pre_push_hook.hook.main())"

Configuration
=============

You can pass configuration parameters to script by setting proper environement variables in ``./.git/hooks/pre-push``

1. Custom Pyflakes configuration file

::

    LINTER_FLAKE_CONFIG="./setup.cfg" python ...

2. Warnings only for changed lines 

::

    CHANGED_LINES_ONLY=1 python ...

Troubleshooting
===============

1. In OSX not prompt question is displayed and after pressing any key EOFError is raised:

Maybe you are not using system Python. E.g. MacPorts have problem with using stdin (
see: http://superuser.com/questions/965133/python2-7-from-macports-stdin-issue).
Try using system Python (``System/Library/Frameworks/Python.framework/Versions/Current/bin/python``)


Development
===========

To run the all tests run::

    tox
