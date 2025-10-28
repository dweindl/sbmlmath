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

We use `pre-commit <https://pre-commit.com/>`_ to run linters and formatters on
the codebase. To enable pre-commit hooks in your development environment, run:

.. code-block:: bash

    pip install pre-commit
    pre-commit install


Running tests
-------------

We use `pytest <https://docs.pytest.org/en/stable/>`_ for testing.

To run the test suite, execute the following command in the project root
directory:

.. code-block:: bash

    pytest

Release process
---------------

Releases are managed via GitHub releases.

To create a new release:

1. Go to the "Releases" section of the GitHub repository.
2. Click on "Draft a new release".
3. Fill in the tag version, release title, and description.

   Version & tag: We follow `Semantic Versioning <https://semver.org/>`_.
   The tag should be in the format ``vX.Y.Z`` (e.g., ``v1.0.0``).
   The release title is ``sbmlmath vX.Y.Z``.
   The package version will be automatically inferred from the tag
   via `setuptools_scm <https://setuptools-scm.readthedocs.io/en/latest/>`__.

   Description: Include a summary of changes, new features, bug fixes,
   and any other relevant information.

4. Publish the release.

   A GitHub Action workflow will automatically build and upload the package to
   PyPI. Ensure that the action completes successfully.
