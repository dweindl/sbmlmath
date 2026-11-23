import subprocess
import sys

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
@pytest.mark.parametrize(
    ("a", "b"),
    (
        (-7, 3),
        (7, 3),
        (-7, -3),
        (7, -3),
        (6, 3),
        (-6, 3),
        (0, 3),
        (-3.5, 2),
    ),
)
def test_quotient(a, b, evaluate):
    """`<quotient/>` truncates toward zero and is consistent with `<rem/>`.

    https://github.com/dweindl/sbmlmath/issues/70
    """

    def cn(x):
        type_ = "integer" if isinstance(x, int) else "real"
        return f'<cn type="{type_}">{x}</cn>'

    def apply(op):
        return (
            '<math xmlns="http://www.w3.org/1998/Math/MathML">'
            f"<apply><{op}/>{cn(a)}{cn(b)}</apply></math>"
        )

    parser = SBMLMathMLParser(evaluate=evaluate)
    q = parser.parse_str(apply("quotient")).doit()
    r = parser.parse_str(apply("rem")).doit()

    assert q == int(a / b)
    assert sp.simplify(b * q + r - a) == 0


@pytest.mark.parametrize("evaluate", (True, False))
def test_quotient_rem_units(evaluate):
    """`<quotient/>` and `<rem/>` work for operands with units."""

    def apply(op):
        return (
            '<math xmlns="http://www.w3.org/1998/Math/MathML" '
            'xmlns:sbml="http://www.sbml.org/sbml/level3/version2/core">'
            f'<apply><{op}/><cn sbml:units="second">-7</cn>'
            '<cn sbml:units="second">3</cn></apply></math>'
        )

    parser = SBMLMathMLParser(evaluate=evaluate)
    assert parser.parse_str(apply("quotient")).doit() == -2
    assert parser.parse_str(apply("rem")).doit() == -1


def test_quotient_symbolic():
    """`<quotient/>` with symbolic operands evaluates correctly after
    substitution.

    https://github.com/dweindl/sbmlmath/issues/70
    """
    mathml = (
        '<math xmlns="http://www.w3.org/1998/Math/MathML">'
        "<apply><quotient/><ci>a</ci><ci>b</ci></apply></math>"
    )
    expr = SBMLMathMLParser().parse_str(mathml)
    a, b = sp.symbols("a b")
    assert expr.free_symbols == {a, b}
    assert expr.subs({a: -7, b: 3}) == -2
    assert expr.subs({a: 7, b: -3}) == -2
    assert expr.subs({a: -7, b: -3}) == 2


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

    # doit: with `evaluate=False`, sympy>=1.15 keeps Boolean constants
    #  in And/Or/Xor
    assert parse("5 && (y > 2)").doit() == (y > 2)
    assert parse("0 && (y > 2)").doit() == sp.false
    assert parse("0 || (y > 2)").doit() == (y > 2)
    assert parse("xor(5, 3)").doit() == sp.false
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
    # doit: unevaluated And keeps the argument order (sympy>=1.15)
    assert expr.doit() == sp.Ne(t, 0) & sp.Ne(x, 0)

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


@pytest.mark.parametrize("evaluate", (True, False))
def test_log_default_base(evaluate):
    """`<log/>` without `<logbase>` defaults to base 10.

    https://github.com/dweindl/sbmlmath/issues/72
    """
    x = sp.Symbol("x")
    parser = SBMLMathMLParser(evaluate=evaluate)
    implicit = parser.parse_str(
        '<math xmlns="http://www.w3.org/1998/Math/MathML">'
        "<apply><log/><ci>x</ci></apply></math>"
    )
    explicit = parser.parse_str(
        '<math xmlns="http://www.w3.org/1998/Math/MathML">'
        '<apply><log/><logbase><cn type="integer">10</cn></logbase>'
        "<ci>x</ci></apply></math>"
    )
    assert implicit == explicit
    assert sp.simplify(implicit.subs(x, 1000).doit()) == 3

    mathml = SBMLMathMLPrinter().doprint(implicit)
    assert parser.parse_str(mathml) == implicit
    ast = libsbml.readMathMLFromString(mathml)
    assert libsbml.formulaToL3String(ast) in {
        "log10(x)",
        "ln(x) / ln(10 dimensionless)",
    }


def test_invalid_input_rejected_without_assertions():
    """Malformed input is rejected also when running with `python -O`."""
    code = (
        "from sbmlmath import SBMLMathMLParser\n"
        "SBMLMathMLParser().parse_str("
        '\'<math xmlns="http://www.w3.org/1998/Math/MathML">'
        "<apply><log/><logbase><cn>2</cn></logbase></apply></math>')\n"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-O", "-c", code],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode != 0
    assert "ValueError: Failed parsing" in result.stderr
    assert "<log> requires an argument." in result.stderr


@pytest.mark.parametrize(
    ("mathml", "message"),
    (
        (
            "<apply><log/><logbase><cn>2</cn></logbase></apply>",
            "<log> requires an argument.",
        ),
        (
            "<apply><log/><logbase><cn>2</cn></logbase>"
            "<logbase><cn>8</cn></logbase></apply>",
            "<log> requires an argument.",
        ),
        (
            "<apply><root/><degree><cn>3</cn></degree></apply>",
            "<root> requires an argument.",
        ),
        (
            "<apply><root/><degree><cn>3</cn></degree>"
            "<degree><cn>8</cn></degree></apply>",
            "<root> requires an argument.",
        ),
        (
            "<apply><log/><cn>2</cn><cn>8</cn></apply>",
            "<log> expects <logbase> as first of 2 operands.",
        ),
        (
            "<piecewise><otherwise><cn>1</cn></otherwise>"
            "<piece><cn>2</cn><true/></piece></piecewise>",
            "<otherwise> must be the last child of <piecewise>.",
        ),
    ),
)
def test_invalid_input(mathml, message):
    """Malformed input raises `ValueError` with a reason."""
    with pytest.raises(ValueError, match="Failed parsing") as exc_info:
        SBMLMathMLParser().parse_str(
            f'<math xmlns="http://www.w3.org/1998/Math/MathML">{mathml}</math>'
        )
    assert message in str(exc_info.value.__cause__)


def test_non_mathml_element():
    """Non-MathML elements raise `ValueError`."""
    with pytest.raises(ValueError, match="Not a MathML element"):
        SBMLMathMLParser().parse_str(
            '<math xmlns="http://www.w3.org/1998/Math/MathML">'
            '<foo xmlns="urn:x"/></math>'
        )
