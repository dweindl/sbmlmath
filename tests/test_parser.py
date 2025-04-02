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


def test_parser_with_name_preprocessor():
    ast_node = libsbml.parseL3Formula("a * b")
    mathml = libsbml.writeMathMLToString(ast_node)

    parser = SBMLMathMLParser()
    parser.preprocess_symbol_name = lambda name, element: f"_{name}"

    sym_expr = parser.parse_str(mathml)
    print(sym_expr)
    assert sym_expr == sp.sympify(sp.sympify("_a * _b"))


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
