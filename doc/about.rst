sbmlmath — a Python library for handling SBML MathML
====================================================

.. image:: https://img.shields.io/pypi/v/sbmlmath
  :target: https://pypi.org/project/sbmlmath/
  :alt: PyPI
.. image:: https://zenodo.org/badge/617871948.svg
  :target: https://doi.org/10.5281/zenodo.14814669
  :alt: DOI

This is a Python library for interconverting `SymPy <https://github.com/sympy/sympy/>`_
expressions and `SBML <https://sbml.org/>`_-MathML.
SBML uses a subset of `MathML <https://www.w3.org/Math/>`_ that this library
aims to support. This is not (intended to be) a general MathML parser.

Main functionality:

* sympy -> SBML MathML

* SBML MathML -> sympy

  * in particular for cases where ``sympy.sympify(libsbml.formulaToL3String(...))``
    won't do the job
    (mind the differences operator precedence between
    sympy/`Python <https://docs.python.org/3/reference/expressions.html#operator-precedence>`_
    and `libsbml L3 formulas <https://synonym.caltech.edu/software/libsbml/5.18.0/docs/formatted/python-api/libsbml-math.html#math-l3>`_!)

  * retaining unit annotations and other ``<ci>`` attributes

**NOTE: This is under development and the API is to be considered unstable**

Python support policy: sbmlmath follows `NEP 29 <https://numpy.org/neps/nep-0029-deprecation_policy.html>`_.

Usage
-----

.. code-block:: python

    from sbmlmath import SBMLMathMLPrinter, SBMLMathMLParser
    import sympy as sp

    sympy_expr = sp.sympify("A ** B + exp(C) * D")
    mathml = SBMLMathMLPrinter().doprint(sympy_expr)
    print(mathml)

    cycled_sympy = SBMLMathMLParser().parse_str(mathml)
    print(cycled_sympy)
    assert sympy_expr == cycled_sympy


Installation
------------

Releases from `PyPI <https://pypi.org/project/sbmlmath/>`_:

.. code-block:: bash

    pip install sbmlmath

The latest development version from GitHub:

.. code-block:: bash

    pip install https://github.com/dweindl/sbmlmath/archive/main.zip


Source code
-----------

The source code is hosted on `GitHub <https://github.com/dweindl/sbmlmath>`_.
