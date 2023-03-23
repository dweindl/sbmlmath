import libsbml
import pytest
import sympy as sp

from sbmlmath import *


@pytest.mark.xfail()
def test_large_mathml():
    """On some setups, lxml.etree.iterparse simply truncates long input
    (>2**15 chars); lxml.etree.parse seems to do fine.
    """
    header = """<?xml version="1.0" encoding="UTF-8"?>
    <math xmlns="http://www.w3.org/1998/Math/MathML" xmlns:sbml="http://www.sbml.org/sbml/level3/version2/core">
      <apply>
        <plus/>
        """
    center = "<ci> some_long_identifier_whose_name_doesnt_matter</ci>\n"
    footer = "</apply></math>"
    mathml_exp = f"{header}{center * 600}{footer}"
    print(len(mathml_exp))
    assert len(mathml_exp) >= 2**15

    assert SBMLMathMLParser().parse_str(mathml_exp) == sp.sympify(
        "600 * some_long_identifier_whose_name_doesnt_matter"
    )


def test_multi_xmlns_works():
    """Test workaround for mathml handling in libsbml, where some xmlns
    declarations may get dropped."""
    xml = SBMLMathMLPrinter().doprint(
        SpeciesSymbol("a", representation_type="sum")
    )
    assert "xmlns:multi" in xml
    ast_node = libsbml.readMathMLFromString(xml)
    new_xml = libsbml.writeMathMLToString(ast_node)
    assert "xmlns:multi" not in new_xml

    sym = SBMLMathMLParser().parse_str(new_xml)
    print(sym)
    assert any(
        (isinstance(x, SpeciesSymbol) and x.representation_type == "sum")
        for x in sym.free_symbols
    )


def test_abs():
    ast = sympy_to_sbml_math(sp.Abs(sp.Symbol("a")))
    assert ast.isFunction()
    assert ast.getType() == libsbml.AST_FUNCTION_ABS


def test_math_dimensionless():
    xml = SBMLMathMLPrinter(literals_dimensionless=False).doprint(sp.Integer(1))
    assert "dimensionless" not in xml

    xml = SBMLMathMLPrinter(literals_dimensionless=True).doprint(sp.Integer(1))
    assert "dimensionless" in xml

    # verify that it's parsable with sbml annotations
    sbml_math_to_sympy(sympy_to_sbml_math(sp.Integer(1)))


@pytest.mark.xfail(strict=True)
def test_libsbml_mathml_drops_multi_xmlns():
    mathml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<math xmlns="http://www.w3.org/1998/Math/MathML" '
        'xmlns:multi="http://www.sbml.org/sbml/level3/version1/multi/version1">'
        '<ci multi:representationType="sum"> a </ci>'
        "</math>"
    )
    assert "xmlns:multi" in mathml
    ast_node = libsbml.readMathMLFromString(mathml)
    new_mathml = libsbml.writeMathMLToString(ast_node)
    print(new_mathml)
    assert "xmlns:multi" in new_mathml


def test_libsbml_mathml_preserves_sbml_xmlns():
    mathml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<math xmlns="http://www.w3.org/1998/Math/MathML" '
        'xmlns:sbml="http://www.sbml.org/sbml/level3/version2/core">'
        '<cn sbml:units="dimensionless">2</cn>'
        "</math>"
    )
    assert "xmlns:sbml" in mathml
    ast_node = libsbml.readMathMLFromString(mathml)
    new_mathml = libsbml.writeMathMLToString(ast_node)
    print(new_mathml)
    assert "xmlns:sbml" in new_mathml
