import libsbml
import pytest
import sympy as sp

from sbmlmath import *


# https://sbml.org/software/libsbml/5.18.0/docs/formatted/python-api/classlibsbml_1_1_a_s_t_node.html
@pytest.mark.parametrize(
    ("formula_str",),
    (
        ("1 + a",),
        ("1.0 + a",),
        ("2.5 * x / 12",),
        ("(3 + a) * b",),
        ("5 - y * 3",),
        ("sqrt(y)",),
        ("pow(a, b)",),
        ("-a",),
        ("-a - b",),
        # ("log(a) + log(x, y)",),
    ),
)
def test_mathmlparser_vs_sympify(formula_str):
    ast_node = libsbml.parseL3Formula(formula_str)
    mathml = libsbml.writeMathMLToString(ast_node)
    parser = SBMLMathMLParser(floats_as_rationals=False, evaluate=True)
    sym_expr = parser.parse_str(mathml)
    print(sym_expr)
    assert sym_expr == sp.sympify(formula_str)


@pytest.mark.parametrize(
    ("a", "b"),
    (
        (-5, 3),
        (5, 3),
        (-5, -3),
        (5, -3),
    ),
)
def test_mathmlparser_rem_vs_piecewise(a, b):
    """`<rem/>` and the pre-L3V2 piecewise expansion of `%` are two
    equivalent encodings of the same operator and must sympify to the
    same (C/truncated-division) result.

    https://github.com/dweindl/sbmlmath/issues/46
    """
    formula = f"{a} % {b}"
    settings = libsbml.L3ParserSettings()

    settings.setParseModuloL3v2(True)
    rem_mathml = libsbml.writeMathMLToString(
        libsbml.parseL3FormulaWithSettings(formula, settings)
    )

    settings.setParseModuloL3v2(False)
    piecewise_mathml = libsbml.writeMathMLToString(
        libsbml.parseL3FormulaWithSettings(formula, settings)
    )

    parser = SBMLMathMLParser(evaluate=True)
    rem_result = parser.parse_str(rem_mathml).doit()
    piecewise_result = parser.parse_str(piecewise_mathml).doit()

    expected = a - b * int(a / b)  # C/truncated-division semantics
    assert rem_result == expected
    assert piecewise_result == expected


def test_parser_with_name_preprocessor():
    ast_node = libsbml.parseL3Formula("a * b")
    mathml = libsbml.writeMathMLToString(ast_node)

    parser = SBMLMathMLParser()
    parser.preprocess_symbol_name = lambda name, element: f"_{name}"

    sym_expr = parser.parse_str(mathml)
    print(sym_expr)
    assert sym_expr == sp.sympify(sp.sympify("_a * _b"))


@pytest.mark.parametrize(
    "expected",
    [
        sp.Integer(10) ** sp.Symbol("x"),
        sp.Float(2.5) ** sp.Symbol("x"),
        sp.Integer(10) ** (2 * sp.Symbol("x")),
        (2 * sp.Symbol("x")) ** sp.Symbol("y"),
    ],
)
def test_power_dimensionless_base_symbolic_exponent(expected):
    mathml = SBMLMathMLPrinter(literals_dimensionless=True).doprint(expected)
    assert 'sbml:units="dimensionless"' in mathml

    result = SBMLMathMLParser(floats_as_rationals=False).parse_str(mathml)

    assert result == expected
    # no pint.Quantity must remain in the expression tree
    assert all(
        isinstance(node, sp.Basic) for node in sp.preorder_traversal(result)
    )


def test_power_scaled_dimensionless_base_symbolic_exponent():
    mathml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<math xmlns="http://www.w3.org/1998/Math/MathML" '
        'xmlns:sbml="http://www.sbml.org/sbml/level3/version2/core">'
        '<apply><power/><cn sbml:units="percent">10</cn><ci>x</ci></apply>'
        "</math>"
    )
    result = SBMLMathMLParser().parse_str(mathml)
    assert sp.simplify(result - sp.Rational(1, 10) ** sp.Symbol("x")) == 0


def test_power_base_with_units_symbolic_exponent():
    mathml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<math xmlns="http://www.w3.org/1998/Math/MathML" '
        'xmlns:sbml="http://www.sbml.org/sbml/level3/version2/core">'
        '<apply><power/><cn sbml:units="mole">10</cn><ci>x</ci></apply>'
        "</math>"
    )
    with pytest.raises(ValueError, match="Failed parsing") as exc_info:
        SBMLMathMLParser().parse_str(mathml)
    assert "units of the result are undefined" in str(exc_info.value.__cause__)


def test_parser_with_custom_assumptions():
    ast_node = libsbml.parseL3Formula("a * b")
    mathml = libsbml.writeMathMLToString(ast_node)

    parser = SBMLMathMLParser()
    sym_expr = parser.parse_str(mathml)
    for symbol in sym_expr.free_symbols:
        assert symbol.is_real is None

    parser.symbol_kwargs = {"real": True}
    sym_expr = parser.parse_str(mathml)
    for symbol in sym_expr.free_symbols:
        assert symbol.is_real is True
