import libsbml
import pytest
import sympy as sp

from sbmlmath import *


def test_large_mathml():
    """
    lxml.etree.iterparse simply truncates long input (>2**15 chars);
    lxml.etree.parse seems to do fine.
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
    if tuple(libsbml.__version__.split(".")) < ("5", "20", "0"):
        assert "xmlns:multi" not in new_xml
    else:
        assert "xmlns:multi" in new_xml

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
    if tuple(libsbml.__version__.split(".")) < ("5", "20", "0"):
        assert "xmlns:multi" not in new_mathml
    else:
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


def test_cycle_csymbol():
    """Check proper handling of csymbols"""
    mathml = """<?xml version="1.0" encoding="UTF-8"?>
        <math xmlns="http://www.w3.org/1998/Math/MathML">
            <csymbol encoding="text" definitionURL="http://www.sbml.org/sbml/symbols/avogadro"> avogadro </csymbol>
        </math>
    """
    sym = SBMLMathMLParser().parse_str(mathml)
    assert isinstance(sym, CSymbol)
    assert "symbols/avogadro" in SBMLMathMLPrinter().doprint(sym)


def test_cfunction():
    mathml = """<?xml version="1.0" encoding="UTF-8"?>
            <math xmlns="http://www.w3.org/1998/Math/MathML">
               <apply xmlns="http://www.w3.org/1998/Math/MathML">
                   <plus/>
                   <apply>
                     <csymbol encoding="text" definitionURL="http://www.sbml.org/sbml/symbols/delay"> delay </csymbol>
                     <ci> Q </ci>
                     <cn type="integer"> 1 </cn>
                   </apply>
                 </apply>
        </math>
    """
    sym = SBMLMathMLParser().parse_str(mathml)
    assert isinstance(sym, sp.Function)
    assert sym.definition_url == "http://www.sbml.org/sbml/symbols/delay"
    assert sym.name == "delay"
    assert sym == delay(sp.Symbol("Q"), sp.Integer(1))


def test_print_cfunction():
    expected = (
        """<?xml version="1.0" encoding="UTF-8"?>\n<math xmlns="http://www.w3.org/1998/Math/MathML" """
        'xmlns:sbml="http://www.sbml.org/sbml/level3/version2/core">\n'
        '<apply><csymbol definitionURL="http://www.sbml.org/sbml/symbols/delay" encoding="text">delay</csymbol>'
        '<ci>Q</ci><cn type="integer" sbml:units="dimensionless">1</cn></apply></math>'
    )
    sym = delay(sp.Symbol("Q"), sp.Integer(1))
    printed_mathml = SBMLMathMLPrinter().doprint(sym)
    assert printed_mathml == expected


def test_integer_overflow():
    """Check whether libsbml still restricts us to 32bit signed integers"""

    def get_mathml(i):
        return f"""<?xml version="1.0" encoding="UTF-8"?>
        <math xmlns="http://www.w3.org/1998/Math/MathML" xmlns:sbml="http://www.sbml.org/sbml/level3/version2/core">
        <cn type="integer">{i}</cn>
        </math>"""

    i = 2**31 - 1
    assert (ast_node := libsbml.readMathMLFromString(get_mathml(i))) is not None
    assert str(i) in libsbml.writeMathMLToString(ast_node)

    # FIXME: change to assert not None, if that restriction is ever lifted
    i = 2**31
    assert libsbml.readMathMLFromString(get_mathml(i)) is None

    assert (
        libsbml.readMathMLFromString(
            SBMLMathMLPrinter().doprint(sp.Integer(2**31 - 1))
        )
        is not None
    )
    assert (
        libsbml.readMathMLFromString(
            SBMLMathMLPrinter().doprint(sp.Integer(-(2**31)))
        )
        is not None
    )

    # would fail as int32, ensure they are printed in a compatible way
    assert (
        libsbml.readMathMLFromString(
            SBMLMathMLPrinter().doprint(sp.Integer(2**31))
        )
        is not None
    )
    assert (
        libsbml.readMathMLFromString(
            SBMLMathMLPrinter().doprint(sp.Integer(-(2**31) - 1))
        )
        is not None
    )
