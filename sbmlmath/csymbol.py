"""Handling of <csymbol> constants"""
from typing import Literal, Optional

import sympy as sp

__all__ = ["CSymbol", "TimeSymbol"]


class CSymbol(sp.Dummy):
    """
    Represents a ``<csymbol>`` element.

    Represents, for example the Avogadro constant, which is defined in SBML as:

    .. code-block:: xml

        <csymbol encoding="text" definitionURL="http://www.sbml.org/sbml/symbols/avogadro"> avogadro </csymbol>

    and can be generated by:

    >>> CSymbol("avogadro", definition_url="http://www.sbml.org/sbml/symbols/avogadro")
    <avogadro(http://www.sbml.org/sbml/symbols/avogadro)>


    See also https://www.w3.org/TR/MathML2/chapter4.html#contm.csymbol.
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

    def __eq__(self, other):
        if not isinstance(other, CSymbol):
            return False

        # if they represent the same value, they are equal
        return self.definition_url == other.definition_url

    def __hash__(self):
        # if we define __eq__, we also need __hash__ to use instances in sympy
        #  expressions
        return hash(self.definition_url)


class TimeSymbol(CSymbol):
    """The current internal simulation time.

    This symbol represents the current simulation time inside the model.

    >>> TimeSymbol("t")
    <t(http://www.sbml.org/sbml/symbols/time)>

    Args:
        name: The name of the symbol.
    """

    def __new__(
        cls,
        name: str,
    ):
        return super().__new__(
            cls,
            name=name,
            definition_url="http://www.sbml.org/sbml/symbols/time",
        )
