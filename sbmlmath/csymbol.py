"""Handling of <csymbol> constants"""

from __future__ import annotations

import sympy as sp

__all__ = ["CSymbol", "TimeSymbol", "avogadro"]


#: The `Avogadro constant <https://en.wikipedia.org/wiki/Avogadro_constant>`_
# as defined in SBML L3V2 section 3.4.6.
SBML_L3V2_AVOGADRO_VALUE = 6.02214179e23


class CSymbol(sp.Dummy):
    """
    Represents a ``<csymbol>`` element.

    Represents, for example the Avogadro constant, which is defined in SBML as:

    .. code-block:: xml

        <csymbol encoding="text" definitionURL="http://www.sbml.org/sbml/symbols/avogadro"> avogadro </csymbol>

    and can be generated by:

    >>> CSymbol("avogadro", definition_url="http://www.sbml.org/sbml/symbols/avogadro")
    <avogadro(http://www.sbml.org/sbml/symbols/avogadro)>
    >>> float(CSymbol("avogadro", definition_url="http://www.sbml.org/sbml/symbols/avogadro"))
    6.02214179e+23

    See also https://www.w3.org/TR/MathML2/chapter4.html#contm.csymbol.
    """

    DEFINITION_URL = None
    _cache = {}
    _definition_url_to_derived_class = {}

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

        # return the matching subtype, depending on the definition URL
        obj = super().__new__(
            cls._definition_url_to_derived_class.get(definition_url, cls),
            *args,
            **kwargs,
        )

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

    def __float__(self):
        if self.definition_url == "http://www.sbml.org/sbml/symbols/avogadro":
            return SBML_L3V2_AVOGADRO_VALUE
        return super().__float__()

    def _eval_evalf(self, prec):
        if self.definition_url == "http://www.sbml.org/sbml/symbols/avogadro":
            return sp.Float(SBML_L3V2_AVOGADRO_VALUE)
        return super()._eval_evalf()

    @classmethod
    def register_subclass(cls, derived_class: type[CSymbol]):
        cls._definition_url_to_derived_class[derived_class.DEFINITION_URL] = (
            derived_class
        )


#: SBML's `Avogadro constant <https://en.wikipedia.org/wiki/Avogadro_constant>`_
avogadro = CSymbol(
    "avogadro", definition_url="http://www.sbml.org/sbml/symbols/avogadro"
)


class TimeSymbol(CSymbol):
    """The current internal simulation time.

    This symbol represents the current simulation time inside the model.

    >>> TimeSymbol("t")
    <t(http://www.sbml.org/sbml/symbols/time)>

    Args:
        name: The name of the symbol.
    """

    DEFINITION_URL = "http://www.sbml.org/sbml/symbols/time"

    def __new__(
        cls,
        name: str,
    ):
        return super().__new__(
            cls,
            name=name,
            definition_url=cls.DEFINITION_URL,
        )


CSymbol.register_subclass(TimeSymbol)
