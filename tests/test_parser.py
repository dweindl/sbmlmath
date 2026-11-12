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


@pytest.mark.parametrize("evaluate", (True, False))
def test_not(evaluate):
    """`<not/>` yields Boolean expressions, also for numeric operands.

    https://github.com/dweindl/sbmlmath/issues/51
    """
    x = sp.Symbol("x")
    parser = SBMLMathMLParser(evaluate=evaluate)

    def parse(formula):
        return parser.parse_str(
            libsbml.writeMathMLToString(libsbml.parseL3Formula(formula))
        )

    # negated relational
    expr = parse("!(x <= 3)")
    assert isinstance(expr, sp.logic.boolalg.Boolean)
    # used to fail with "Illegal operator Piecewise"
    expr.to_nnf()
    if evaluate:
        assert expr == (x > 3)
    else:
        assert expr == sp.Not(x <= 3, evaluate=False)

    # printer round trip
    expr = sp.Piecewise((1, sp.Not(x <= 3, evaluate=evaluate)), (0, True))
    assert (
        SBMLMathMLParser(evaluate=evaluate, ignore_units=True).parse_str(
            SBMLMathMLPrinter().doprint(expr)
        )
        == expr
    )

    # in a numeric context, it is converted to a number
    expr = parse("!(x <= 3) + 1")
    assert expr.subs(x, 4) == 2
    assert expr.subs(x, 3) == 1

    # numeric operands: 0 is false, everything else is true
    #  (SBML L3V2 Section 3.4.4)
    assert parse("!0").simplify() == sp.true
    assert parse("!5").simplify() == sp.false
    assert parse("!-0.5").simplify() == sp.false
    expr = parse("!(x + 1)")
    assert isinstance(expr, sp.logic.boolalg.Boolean)
    assert expr.subs(x, -1) == sp.true
    assert expr.subs(x, 0) == sp.false
    assert expr.subs(x, 1) == sp.false


@pytest.mark.parametrize("evaluate", (True, False))
def test_logical_operators_numeric_operands(evaluate):
    """Numeric operands of `and`/`or`/`xor`/`implies` are converted to
    Booleans: 0 is false, everything else is true (SBML L3V2 Section 3.4.4).
    """
    x, y = sp.symbols("x y")
    parser = SBMLMathMLParser(evaluate=evaluate)

    def parse(formula):
        return parser.parse_str(
            libsbml.writeMathMLToString(libsbml.parseL3Formula(formula))
        )

    assert parse("5 && (y > 2)") == (y > 2)
    assert parse("0 && (y > 2)") == sp.false
    assert parse("0 || (y > 2)") == (y > 2)
    assert parse("xor(5, 3)") == sp.false
    assert parse("implies(0, y > 2)").simplify() == sp.true
    assert parse("and(5)") == sp.true
    assert parse("or(0)") == sp.false

    for formula, expected in (
        ("(x + 1) && (y > 2)", sp.And(sp.Ne(x + 1, 0), y > 2)),
        ("(x + 1) || (y > 2)", sp.Or(sp.Ne(x + 1, 0), y > 2)),
        ("xor(x + 1, y > 2)", sp.Xor(sp.Ne(x + 1, 0), y > 2)),
        ("or(x + 1)", sp.Ne(x + 1, 0)),
    ):
        # doit: unevaluated `x + 1` has a different argument order
        assert parse(formula).doit() == expected


@pytest.mark.parametrize("evaluate", (True, False))
def test_symbols_in_boolean_context(evaluate):
    """Symbols in Boolean contexts are numeric, unless bound by a lambda.

    https://github.com/dweindl/sbmlmath/issues/57
    """
    x, y, z = sp.symbols("x y z")
    parser = SBMLMathMLParser(evaluate=evaluate, ignore_units=True)

    def parse(formula):
        return parser.parse_str(
            libsbml.writeMathMLToString(libsbml.parseL3Formula(formula))
        )

    for formula, expected in (
        ("x && (y > 2)", sp.Ne(x, 0) & (y > 2)),
        ("not(x)", sp.Eq(x, 0)),
        ("and(x)", sp.Ne(x, 0)),
        ("implies(x, y)", sp.Implies(sp.Ne(x, 0), sp.Ne(y, 0))),
        ("piecewise(1, x, 0)", sp.Piecewise((1, sp.Ne(x, 0)), (0, True))),
        (
            "and(piecewise(y, y == 2, 0), z > 0)",
            sp.Eq(y, 2) & sp.Ne(y, 0) & (z > 0),
        ),
    ):
        expr = parse(formula)
        assert expr.simplify() == expected.simplify()
        # printer round trip
        assert parser.parse_str(SBMLMathMLPrinter().doprint(expr)) == expr

    # numeric values can be substituted
    expr = parse("x && (y > 2)")
    assert expr.subs({x: 2, y: 3}) == sp.true
    assert expr.subs({x: 0, y: 3}) == sp.false
    expr = parse("piecewise(1, x, 0)")
    assert expr.subs(x, 2) == 1
    assert expr.subs(x, 0) == 0

    # csymbols are numeric
    expr = parse("time && x")
    (t,) = expr.atoms(CSymbol)
    assert expr == sp.Ne(t, 0) & sp.Ne(x, 0)

    # bound variables may be Boolean, depending on the call site
    #  (SBML semantic test suite case 01486)
    my_not = parse("lambda(x, not(x))")
    assert my_not == sp.Lambda(x, sp.Not(x))
    assert my_not(sp.false) == sp.true
    assert my_not(sp.true) == sp.false
    # ... but other symbols in the lambda body are numeric
    expr = parse("lambda(x, x && y)")
    assert expr == sp.Lambda(x, x & sp.Ne(y, 0))
    # bound variables are reset after parsing the lambda
    parse("lambda(x, not(x))")
    assert parse("not(x)").simplify() == sp.Eq(x, 0)


@pytest.mark.parametrize("evaluate", (True, False))
def test_logical_operators_piecewise_operands(evaluate):
    """Piecewise operands of logical operators are converted to Booleans.

    https://github.com/dweindl/sbmlmath/issues/53
    """
    x, y, z = sp.symbols("x y z")
    parser = SBMLMathMLParser(evaluate=evaluate, ignore_units=True)

    def parse(formula):
        return parser.parse_str(
            libsbml.writeMathMLToString(libsbml.parseL3Formula(formula))
        )

    for formula, expected in (
        ("and(piecewise(1, x > 1, 0), y > 2)", (x > 1) & (y > 2)),
        ("not(piecewise(1, x > 1, 0))", x <= 1),
        (
            "or(piecewise(x + 1, x > 1, y - 1), z > 0)",
            ((x > 1) & sp.Ne(x + 1, 0))
            | ((x <= 1) & sp.Ne(y - 1, 0))
            | (z > 0),
        ),
        # Boolean-valued pieces
        (
            "and(piecewise(x > 2, x > 1, y > 3), z > 0)",
            (((x > 1) & (x > 2)) | ((x <= 1) & (y > 3))) & (z > 0),
        ),
        # piecewise nested in a numeric expression: always non-zero
        ("and(piecewise(1, x > 1, 0) + 1, y > 2)", y > 2),
    ):
        expr = parse(formula)
        # doit: unevaluated `x + 1` has a different argument order
        assert expr.doit() == expected
        # printer round trip
        assert (
            parser.parse_str(SBMLMathMLPrinter().doprint(expr)).doit()
            == expected
        )

    # ITE as piecewise condition is printed as <piecewise> and parsed into
    #  an equivalent And/Or expression
    expr = sp.Piecewise(
        (1, sp.ITE(x > 1, y > 2, sp.ITE(x < 0, y < 1, False))), (0, True)
    )
    parsed = parser.parse_str(SBMLMathMLPrinter().doprint(expr))
    assert not parsed.has(sp.ITE)
    for x_val in (-1, 0.5, 2):
        for y_val in (0, 1.5, 3):
            subs = {x: x_val, y: y_val}
            assert parsed.subs(subs) == expr.subs(subs)

    # overlapping conditions: the first matching piece applies
    expr = parse("or(piecewise(0, x > 0, 1, x > -1, 0), z > 0)")
    assert expr.subs({x: 0.5, z: -1}) == sp.false
    assert expr.subs({x: -0.5, z: -1}) == sp.true
    assert expr.subs({x: -1.5, z: -1}) == sp.false


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
