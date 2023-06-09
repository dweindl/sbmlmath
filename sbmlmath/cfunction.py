"""Handling of <csymbol> functions"""
import sympy as sp
from sympy.core.function import UndefinedFunction

__all__ = ["CFunction", "delay", "rate_of"]


class CFunction(UndefinedFunction):
    """
    Represents <csymbol> functions

    examples: rateOf, delay, distributions from distrib package
    https://synonym.caltech.edu/documents/specifications/level-3/version-1/distrib/


    See also https://www.w3.org/TR/MathML2/chapter4.html#contm.deffun
    """

    _cache = {}

    def __new__(
        cls,
        *args,
        definition_url: str,
        encoding: str = "text",
        **kwargs,
    ):
        # Cache instances.
        # If not done: (CFunction("A", definition_url="x")
        #               == CFunction("A", definition_url="y")) == False
        if not (name := kwargs.get("name")):
            name = args[0]
        cache_key = (name, definition_url, encoding)
        if cached := cls._cache.get(cache_key):
            return cached

        obj = super().__new__(cls, *args, **kwargs)

        # ensure there are no collisions with super() attributes
        assert not hasattr(obj, "definition_url")
        assert not hasattr(obj, "encoding")
        obj.definition_url = definition_url
        obj.encoding = encoding

        cls._cache[cache_key] = obj

        return obj


# SBML-defined functions
delay = CFunction("delay", definition_url="http://www.sbml.org/sbml/symbols/delay")
rate_of = CFunction("rateOf", definition_url="http://www.sbml.org/sbml/symbols/rateOf")
