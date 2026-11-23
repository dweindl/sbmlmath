import itertools
import subprocess
import sys

import libsbml
import pytest
import sympy as sp

from sbmlmath import *
from sbmlmath.mathml_parser import _expand_piecewise_relationals


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
    # the unit conversion factor is applied, also with `evaluate=False`
    assert result.base.is_Number


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


@pytest.mark.parametrize("evaluate", (True, False))
def test_log_with_base_is_differentiable(evaluate):
    """`<log/>` with `<logbase>` doesn't yield SymPy's two-argument `log`.

    SymPy's `diff` and code printers ignore the base of an unevaluated
    `log(x, base)`.
    """
    x = sp.Symbol("x")
    parser = SBMLMathMLParser(evaluate=evaluate)
    expr = parser.parse_str(
        '<math xmlns="http://www.w3.org/1998/Math/MathML">'
        '<apply><log/><logbase><cn type="integer">2</cn></logbase>'
        "<ci>x</ci></apply></math>"
    )
    assert all(len(f.args) == 1 for f in expr.atoms(sp.log))
    assert sp.simplify(expr.diff(x) - 1 / (x * sp.log(2))) == 0
    assert sp.ccode(expr) == "log(x)/M_LN2"


@pytest.mark.parametrize("evaluate", (True, False))
def test_relational_operators_boolean_operands(evaluate):
    """Boolean operands of relational operators are converted to numbers.

    https://github.com/dweindl/sbmlmath/issues/65
    """
    x, a = sp.symbols("x a", real=True)
    parser = SBMLMathMLParser(
        evaluate=evaluate, ignore_units=True, symbol_kwargs={"real": True}
    )

    def parse(formula):
        return parser.parse_str(
            libsbml.writeMathMLToString(libsbml.parseL3Formula(formula))
        )

    # (relational, whether it is equivalent to `{b}`)
    #  (function syntax, as libsbml parses `(a > b) == c` as
    #  `a > b && b == c`)
    relationals = [
        ("gt({b}, 0.5)", True),
        ("lt(0.5, {b})", True),
        ("geq({b}, 1)", True),
        ("leq({b}, 0)", False),
        ("eq({b}, 1)", True),
        ("eq(1, {b})", True),
        ("neq({b}, 1)", False),
        ("eq({b}, true)", True),
        # n-ary
        ("gt(2, {b}, 0.5)", True),
        ("eq(1, {b}, true)", True),
    ]
    # Boolean expressions with piecewise, equivalent to `x > {rhs}`
    booleans = (
        "piecewise(true, x > {rhs}, false)",
        "piecewise(piecewise(true, x > {rhs}, false), x > {rhs} - 1, false)",
        "piecewise(x > {rhs}, x > {rhs} - 2, false)",
        "gt(piecewise(true, x > {rhs}, false), 0.5)",
    )
    for b, rhs, (rel, equivalent) in itertools.product(
        booleans, ("a", "0"), relationals
    ):
        rel = rel.format(b=b.format(rhs=rhs))
        for formula, values in (
            (rel, (sp.true, sp.false)),
            (f"piecewise(5, {rel}, 7)", (5, 7)),
        ):
            expr = parse(formula)
            expr_rt = parser.parse_str(SBMLMathMLPrinter().doprint(expr))
            for x_val, x_gt_a in ((1, True), (-0.5, False), (-3, False)):
                expected = values[0] if x_gt_a == equivalent else values[1]
                for e in (expr, expr_rt):
                    assert e.subs({x: x_val, a: 0}) == expected, (formula, e)

    # Boolean literal operands of n-ary relational operators
    assert parse("gt(2, true, 0.5)").doit() == sp.true
    assert parse("eq(1, true, 1)").doit() == sp.true

    # relational with piecewise operand in a numerical context
    expr = parse("gt(piecewise(2, x > a, 0), 1) + 1")
    assert not expr.has(sp.ITE)
    assert expr.subs({x: 1, a: 0}) == 2
    assert expr.subs({x: -1, a: 0}) == 1

    # Boolean-valued piecewise arguments of user-defined functions are kept,
    #  as the function may expect a Boolean
    lam = parse("lambda(b, piecewise(1, b, 0))")
    expr = parse("f(piecewise(true, x > a, false))")
    expr = expr.replace(expr.func, lam)
    assert expr.subs({x: 1, a: 0}) == 1
    assert expr.subs({x: -1, a: 0}) == 0

    # operands of the expanded relationals are evaluated only if requested
    expr = parse("piecewise(1, piecewise(x, x > a, 0) + 0 > 0.5, 0)")
    assert expr.has(sp.Add) is not evaluate
    assert expr.subs({x: 1, a: 0}) == 1
    assert expr.subs({x: 0.25, a: 0}) == 0


def test_piecewise_relational_conditions_not_expandable():
    """Relationals that can't be evaluated in all pieces.

    E.g., due to units or non-real values in non-selected pieces.
    """
    parser = SBMLMathMLParser(evaluate=False)
    x, a = sp.symbols("x a")

    def parse(formula):
        return parser.parse_str(
            libsbml.writeMathMLToString(libsbml.parseL3Formula(formula))
        )

    for formula in (
        "piecewise(1, gt(piecewise(2 second, x > a, 0 second), 1 second), 0)",
        "piecewise(1, gt(piecewise(x, x > a, 0), 2 dimensionless), 0)",
    ):
        assert isinstance(parse(formula), sp.Piecewise)

    # non-real values are kept in unevaluated relationals
    for formula, non_real_rel in (
        (
            "piecewise(1, gt(1/piecewise(0, x > a, 1), 0.5), 0)",
            sp.StrictGreaterThan(
                sp.Pow(0, -1, evaluate=False),
                sp.Rational(1, 2),
                evaluate=False,
            ),
        ),
        (
            "piecewise(1, gt(ln(piecewise(0, x > a, 1)), -1), 0)",
            sp.StrictGreaterThan(
                sp.log(0, evaluate=False), -1, evaluate=False
            ),
        ),
    ):
        result = parse(formula)
        assert result.args[0].expr == 1
        assert result.args[0].cond == (x <= a) | ((x > a) & non_real_rel)
        assert result.args[1] == (0, True)


def test_expand_piecewise_relationals_skips_cfunctions():
    """Piecewise arguments of CFunctions are not expanded.

    Their semantics are unknown to the expansion.
    """
    x = sp.Symbol("x", real=True)
    pw = sp.Piecewise((2, x > 0), (3, True))
    for rel in (rate_of(pw) > 2.5, rate_of(pw) + 1 > 2.5):
        assert _expand_piecewise_relationals(rel) == rel
    # the piecewise outside the CFunction is expanded
    rel = rate_of(pw) > pw
    assert _expand_piecewise_relationals(rel) == (
        (x > 0) & (rate_of(pw) > 2) | (x <= 0) & (rate_of(pw) > 3)
    )


@pytest.mark.parametrize(
    ("mathml", "expected"),
    (
        ("<!-- c --><ci>x</ci>", sp.Symbol("x")),
        ("<?pi foo?><ci>x</ci>", sp.Symbol("x")),
        (
            "<apply><!-- c --><plus/><ci>x</ci><ci>y</ci></apply>",
            sp.Symbol("x") + sp.Symbol("y"),
        ),
        (
            "<apply><plus/><!-- c --><ci>x</ci><ci>y</ci><!-- c --></apply>",
            sp.Symbol("x") + sp.Symbol("y"),
        ),
        ("<cn>1<!-- c -->2</cn>", sp.Integer(12)),
        (
            '<cn type="e-notation">1<!-- c --><sep/><!-- c -->2</cn>',
            sp.Float(100),
        ),
        (
            "<piecewise><!-- c --><piece><cn>1</cn><true/></piece>"
            "<otherwise><cn>2</cn></otherwise><!-- c --></piecewise>",
            sp.Piecewise((1, True), (2, True)),
        ),
    ),
)
def test_comments_and_processing_instructions_ignored(mathml, expected):
    """XML comments and processing instructions are ignored."""
    assert (
        SBMLMathMLParser(evaluate=True).parse_str(
            f'<math xmlns="http://www.w3.org/1998/Math/MathML">{mathml}</math>'
        )
        == expected
    )


def test_parse_does_not_repeatedly_clear_sympy_cache(monkeypatch):
    """Changing sympy's global `evaluate` flag clears the sympy cache.

    https://github.com/dweindl/sbmlmath/issues/71
    """
    import sympy.core.parameters

    n_clear_cache = 0
    clear_cache = sympy.core.parameters.clear_cache

    def counting_clear_cache():
        nonlocal n_clear_cache
        n_clear_cache += 1
        clear_cache()

    monkeypatch.setattr(
        sympy.core.parameters, "clear_cache", counting_clear_cache
    )
    mathml = libsbml.writeMathMLToString(
        libsbml.parseL3Formula(
            "a * b / (c + d^2) - e + root(3, f) + piecewise(1, t > 2, 0)"
            " + piecewise(1, (a && b) || !c || lt(1, x, 3), 0)"
        )
    )
    parser = SBMLMathMLParser(evaluate=False)

    # entering and leaving `sp.evaluate(False)` once
    parser.parse_str(mathml)
    assert n_clear_cache == 2

    def count_clear_cache(formula):
        nonlocal n_clear_cache
        n_clear_cache = 0
        parser.parse_str(
            libsbml.writeMathMLToString(libsbml.parseL3Formula(formula))
        )
        return n_clear_cache

    # no operators that depend on the global flag
    for formula in ("a", "2", "1.5", "sin(a < b)", "lt(1, x, 3)", "!a"):
        assert count_clear_cache(formula) == 0, formula

    # non-symbol operands in Boolean contexts are converted under the
    #  caller's flag, which is changed once per Boolean operator
    assert count_clear_cache("and(a * b, c, d * e, f + 1)") == 4

    # no changes to the global flag at all
    with sp.evaluate(False):
        n_clear_cache = 0
        parser.parse_str(mathml)
        assert n_clear_cache == 0


def test_evaluate_false_unaffected_constructions():
    """`evaluate=False` only applies to the parsed operators."""
    parser = SBMLMathMLParser(evaluate=False)
    x = sp.Symbol("x")

    # function evaluation
    mathml = (
        '<math xmlns="http://www.w3.org/1998/Math/MathML"><apply>'
        '<csymbol encoding="text" '
        'definitionURL="http://www.sbml.org/sbml/symbols/rateOf">rateOf'
        "</csymbol><cn>1</cn></apply></math>"
    )
    assert parser.parse_str(mathml) == 0

    # n-ary relational operators are chained without a leading `True`
    mathml = libsbml.writeMathMLToString(libsbml.parseL3Formula("lt(1, x, 3)"))
    assert parser.parse_str(mathml).args == (
        sp.StrictLessThan(1, x, evaluate=False),
        sp.StrictLessThan(x, 3, evaluate=False),
    )


@pytest.mark.parametrize("evaluate", (True, False))
def test_delayed_piecewise_in_condition(evaluate):
    """Delayed piecewise expressions in piecewise conditions are rejected.

    sympy would evaluate their conditions at the current time.
    """
    parser = SBMLMathMLParser(evaluate=evaluate, ignore_units=True)

    def parse(formula):
        return parser.parse_str(
            libsbml.writeMathMLToString(libsbml.parseL3Formula(formula))
        )

    for formula in (
        "piecewise(1, delay(piecewise(2, x > 0, 3), 1) > 2.5, 0)",
        "piecewise(1, delay(piecewise(2, x > 0, 3), 1), 0)",
        "piecewise(1, f(delay(piecewise(2, x > 0, 3), 1)) > 2.5, 0)",
        "gt(delay(piecewise(2, x > 0, 3), 1), 2.5) + 1",
        "piecewise(1, delay(piecewise(2, x > 0, 3), 1) > 2.5 && y > 0, 0)",
        # quotient and rem create piecewise conditions with their operands
        "quotient(delay(piecewise(2, x > 0, 3), 1), 2)",
        "rem(5, delay(piecewise(2, x > 0, 3), 1))",
        # Booleans and quotient are represented as piecewise
        "piecewise(1, delay(x > 0, 1), 0)",
        "piecewise(1, delay(quotient(x, 2), 1) > 0, 0)",
    ):
        with pytest.raises(NotImplementedError, match="delay"):
            parse(formula)

    # pint.Quantity operands
    parser.ignore_units = False
    with pytest.raises(NotImplementedError, match="delay"):
        parse(
            "quotient(delay(piecewise(2, x > 0, 3), 1) * 2 dimensionless, 2)"
        )
    parser.ignore_units = True

    # delay csymbols are identified by their definitionURL, not by their name
    mathml = libsbml.writeMathMLToString(
        libsbml.parseL3Formula(
            "piecewise(1, delay(piecewise(2, x > 0, 3), 1) > 2.5, 0)"
        )
    )
    assert mathml.count("> delay <") == 1
    with pytest.raises(NotImplementedError, match="delay"):
        parser.parse_str(mathml.replace("> delay <", "> mydelay <"))

    # still supported
    x, y = sp.symbols("x y")
    pw = sp.Piecewise((2, x > 0), (3, True))
    assert parse("delay(piecewise(2, x > 0, 3), 1) + 1").has(delay(pw, 1))
    assert not parse("piecewise(1, delay(x, 1) > 0, 0)").has(sp.ITE)
    assert parse("piecewise(delay(piecewise(2, x > 0, 3), 1), y > 0, 0)").has(
        delay(pw, 1)
    )
    # piecewise delay time: evaluated at the current time
    #  (with evaluate=False, sympy's piecewise folding fails)
    if not evaluate:
        return
    expr = parse("piecewise(1, delay(x, piecewise(1, y > 0, 2)) > 2.5, 0)")
    for y_val, delay_time in ((1, 1), (-1, 2)):
        assert expr.subs({y: y_val, delay(x, delay_time): 3}) == 1
        assert expr.subs({y: y_val, delay(x, delay_time): 2}) == 0
