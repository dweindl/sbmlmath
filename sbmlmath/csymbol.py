"""<csymbol> related functionality"""
from typing import Literal, Optional

import sympy as sp

__all__ = ["CSymbol"]


class CSymbol(sp.Dummy):
    """
    Represents a <csymbol> element.

    Represents e.g.:
    ``<csymbol encoding="text" definitionURL="http://www.sbml.org/sbml/symbols/avogadro"> avogadro </csymbol>``

    See also https://www.w3.org/TR/MathML2/chapter4.html#contm.deffun
    """

    _cache = {}

    def __new__(
        cls,
        *args,
        definition_url: str,
        encoding: str,
        **kwargs,
    ):
        # Cache instances.
        # If not done: (CSymbol("A") == CSymbol("A")) == False
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

    def __repr__(self):
        return f"<{self.name}({self.definition_url})>"
