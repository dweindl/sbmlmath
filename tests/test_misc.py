from sbmlmath import *
import pytest


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

    assert SBMLMathMLParser().parse_str(mathml_exp) \
           == sp.sympify("600 * some_long_identifier_whose_name_doesnt_matter")


def test_multi_xmlns_works():
    """Test workaround for mathml handling in libsbml, where some xmlns
    declarations may get dropped."""
    xml = MyMathMLContentPrinter().doprint(
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
