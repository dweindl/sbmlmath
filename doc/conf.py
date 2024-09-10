# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
import zlib


def get_libsbml_inventory(
    filename: str = "libsbml.inv",
    base_url: str = "https://sbml.org/software/libsbml/5.18.0/docs/formatted/python-api/",
) -> tuple[str, str]:
    """Create the libsbml inventory file for use with intersphinx."""
    inventory_header = (
        "# Sphinx inventory version 2\n"
        "# Project: libsbml\n"
        "# Version: 5.18.0\n"
        "# The remainder of this file is compressed using zlib.\n"
    )
    inventory_content = (
        "libsbml.ASTNode py:class -1 classlibsbml_1_1_a_s_t_node.html libsbml.ASTNode\n"
        "libsbml.SBase py:class -1 classlibsbml_1_1_s_base.html libsbml.SBase\n"
    )
    compressed_content = zlib.compress(inventory_content.encode("utf-8"))

    with open(filename, "wb") as f:
        f.write(inventory_header.encode("utf-8"))
        f.write(compressed_content)

    return (base_url, filename)


project = "sbmlmath"
copyright = "2024, Daniel Weindl"
author = "Daniel Weindl"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.autosummary",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx_autodoc_typehints",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


autodoc_default_options = {
    "members": None,
    "imported-members": ["sbmlmath"],
    "inherited-members": False,
    "show-inheritance": None,
}

# sphinx-autodoc-typehints options
# https://github.com/tox-dev/sphinx-autodoc-typehints
always_use_bars_union = True
typehints_fully_qualified = False

# autodoc_class_signature = "separated"

intersphinx_mapping = {
    "sympy": ("https://docs.sympy.org/latest/", None),
    "pint": ("https://pint.readthedocs.io/en/stable/", None),
    "python": ("https://docs.python.org/3", None),
    "libsbml": get_libsbml_inventory(),
}

typehints_document_rtype = True
autodoc_typehints = "description"

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "alabaster"
html_static_path = ["_static"]
