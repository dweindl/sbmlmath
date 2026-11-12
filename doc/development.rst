Development
===========

Contributing to sbmlmath
------------------------

We welcome contributions from the community.
If you're interested in contributing to the project, please follow these steps:

1. Fork the repository on GitHub.
2. Create a new branch for your feature or bug fix.
3. Make your changes and commit them with clear messages.
4. Push your changes to your forked repository.
5. Open a pull request against the main repository.

Before submitting a pull request, please ensure that your code adheres to the
project's coding standards and includes appropriate tests.


Development setup
-----------------

Install the package in editable mode with the test dependencies
and enable the `pre-commit <https://pre-commit.com/>`_ hooks
(linters and formatters):

.. code-block:: bash

    pip install -e .[test]
    pre-commit install


Running tests
-------------

We use `pytest <https://docs.pytest.org/en/stable/>`_ for testing.
This includes the doctests in ``sbmlmath/``.
To run the test suite, execute the following command in the project root
directory:

.. code-block:: bash

    pytest

The tests based on the
`SBML Test Suite <https://github.com/sbmlteam/sbml-test-suite/>`_
are skipped unless ``SBML_TEST_SUITE_ROOT`` points to a checkout of it:

.. code-block:: bash

    git clone --depth=1 https://github.com/sbmlteam/sbml-test-suite/
    SBML_TEST_SUITE_ROOT=$(pwd)/sbml-test-suite pytest


Building the documentation
--------------------------

.. code-block:: bash

    pip install -r doc/rtd_requirements.txt
    cd doc && make html


Release process
---------------

Releases are managed via GitHub releases.

To create a new release:

1. Ensure that the tests on ``main`` pass
   and that ``CITATION.cff`` is up to date.
2. Go to the "Releases" section of the GitHub repository.
3. Click on "Draft a new release".
4. Fill in the tag version, release title, and description.

   Version & tag: We follow `Semantic Versioning <https://semver.org/>`_.
   The tag should be in the format ``vX.Y.Z`` (e.g., ``v1.0.0``).
   The release title is ``sbmlmath vX.Y.Z``.
   The package version will be automatically inferred from the tag
   via `setuptools_scm <https://setuptools-scm.readthedocs.io/en/latest/>`__.

   Description: Use "Generate release notes" and edit as needed.
   The release notes serve as the changelog.

5. Publish the release.

   A GitHub Action workflow will automatically build and upload the package to
   PyPI. Ensure that the action completes successfully.
   Zenodo archives the release automatically.

6. Merge the version update pull request that the conda-forge bot opens at
   https://github.com/conda-forge/sbmlmath-feedstock.
   Update the recipe if the dependencies have changed.
