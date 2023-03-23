import libsbml
import pytest
import sympy as sp
from sbmlmath import *

# https://sbml.org/software/libsbml/5.18.0/docs/formatted/python-api/classlibsbml_1_1_a_s_t_node.html
@pytest.mark.parametrize(
    ('formula_str',),
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
    )
)
def test_mathmlparser_vs_sympify(formula_str):
    ast_node = libsbml.parseL3Formula(formula_str)
    mathml = libsbml.writeMathMLToString(ast_node)
    parser = SBMLMathMLParser()
    sym_expr = parser.parse_str(mathml)
    print(sym_expr)
    assert sym_expr == sp.sympify(formula_str)

