from sbmlmath.csymbol import *


def test_time_symbol():
    assert TimeSymbol("t") is TimeSymbol("t")

    assert TimeSymbol("t") == TimeSymbol("time")
    assert TimeSymbol("t") is not TimeSymbol("time")

    t1, t2 = TimeSymbol("t"), TimeSymbol("time")
    eight_t = t1 + t2 + 3 * t1 + 3 * t2
    # is the result defined?
    assert eight_t in [8 * t1, 8 * t2]
