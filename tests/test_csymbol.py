import sympy as sp

from sbmlmath import sbml_math_to_sympy, sympy_to_sbml_math
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
