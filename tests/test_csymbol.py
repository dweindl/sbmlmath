import sympy as sp
from sympy.core.function import UndefinedFunction

from sbmlmath.cfunction import *
from sbmlmath.cfunction import DEF_URL_DELAY, DEF_URL_RATE_OF
from sbmlmath.csymbol import *


def test_time_symbol():
    assert TimeSymbol("t") is TimeSymbol("t")

    assert TimeSymbol("t") == TimeSymbol("time")
    assert TimeSymbol("t") is not TimeSymbol("time")

    t1, t2 = TimeSymbol("t"), TimeSymbol("time")
    eight_t = t1 + t2 + 3 * t1 + 3 * t2
    # is the result defined?
    assert eight_t in [8 * t1, 8 * t2]

    # test with a non-cached symbol (i.e. a new name)
    assert isinstance(
        CSymbol(
            "new_name_for_time",
            definition_url=TimeSymbol.DEFINITION_URL,
        ),
        TimeSymbol,
    )
    assert TimeSymbol("new_name_for_time2") == CSymbol(
        "new_name_for_time3",
        definition_url=TimeSymbol.DEFINITION_URL,
    )

    assert (2 * t1).has(t1) is True
    assert (2 * t1).has(TimeSymbol) is True
    assert (2 * t1).has(CSymbol) is True
    assert (sp.sympify("l * e * e * t")).has(TimeSymbol) is False


def test_cfunction():
    rate_of = CFunction("rateOf", definition_url=DEF_URL_RATE_OF)
    # test that the cache works
    assert rate_of is CFunction("rateOf", definition_url=DEF_URL_RATE_OF)
    # test that definition URL is considered, not only the name
    assert rate_of is not CFunction("rateOf", definition_url=DEF_URL_DELAY)

    assert rate_of == CFunction("rateOf", definition_url=DEF_URL_RATE_OF)
    assert rate_of != CFunction("rateOf", definition_url=DEF_URL_DELAY)
    assert isinstance(rate_of, CFunction)
    assert isinstance(rate_of, RateOf)
    assert not isinstance(rate_of, delay)
    a, b = sp.symbols("a b")
    assert (rate_of(a) * 4).has(rate_of) is True
    assert (rate_of(a) * 4).has(RateOf("rAteOf")) is True
    assert rate_of(a) == rate_of(a)
    assert rate_of(a) != rate_of(b)
    assert (rate_of(a) * 4).has(RateOf) is False

    assert UndefinedFunction(rate_of.name) != rate_of
    assert UndefinedFunction(rate_of.name)(a).has(rate_of) is False

    assert rate_of(1) == 0
    assert rate_of(1, evaluate=False).has(rate_of) is True
    assert rate_of(1, evaluate=False).doit() == 0


def test_avogadro():
    from sbmlmath import avogadro

    assert avogadro.evalf() == float(avogadro)
