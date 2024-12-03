"""Handling of ``<csymbol>`` functions"""

from __future__ import annotations

from sympy import Number
from sympy.core.function import UndefinedFunction

__all__ = ["CFunction", "delay", "rate_of", "Delay", "RateOf"]

DEF_URL_BASE = "http://www.sbml.org/sbml/symbols/"
DEF_URL_RATE_OF = DEF_URL_BASE + "rateOf"
DEF_URL_DELAY = DEF_URL_BASE + "delay"


class CFunction(UndefinedFunction):
    """
    Represents ``<csymbol>`` functions.

    Examples: :func:`rateOf() <rate_of>`, :func:`delay`,
    distributions from the `distrib package
    <https://synonym.caltech.edu/documents/specifications/level-3/version-1/distrib/>`_.


    See also https://www.w3.org/TR/MathML2/chapter4.html#contm.deffun.
    """

    DEFINITION_URL = None
    _cache = {}
    _definition_url_to_derived_class = {}

    def __new__(
        cls: type[CFunction],
        *args,
        definition_url: str = None,
        encoding: str = "text",
        **kwargs,
    ):
        definition_url = definition_url or cls.DEFINITION_URL
        if definition_url is None:
            raise ValueError("definition_url must be provided")

        # Cache instances.
        # If not done: (CFunction("A", definition_url="x")
        #               == CFunction("A", definition_url="y")) == False
        if not (name := kwargs.get("name")):
            if not len(args):
                raise ValueError("name argument must be provided")
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
        if hasattr(cls, "eval"):
            obj.eval = cls.eval

        cls._cache[cache_key] = obj

        return obj

    def __eq__(self, other):
        if not isinstance(other, CFunction):
            return False

        # if they represent the same value, they are equal
        return self.definition_url == other.definition_url

    def __hash__(self):
        return hash(
            (
                self.__class__.__name__,
                self.DEFINITION_URL,
                self.definition_url,
                self.name,
            )
        )

    @classmethod
    def register_subclass(cls, derived_class: type[CFunction]):
        cls._definition_url_to_derived_class[derived_class.DEFINITION_URL] = (
            derived_class
        )


# Derived classes for specific SBML functions
class Delay(CFunction):
    """Produces a SBML ``delay()`` function.

    Usually, it's preferable to use the :func:`delay` function.
    This class can be used if a *delay* function with a different name is
    needed.

    Examples:
        >>> from sympy.abc import a
        >>> my_delay = Delay("my_delay")
        >>> my_delay(a)
        my_delay(a)
        >>> delay(a) == my_delay(a)
        True
    """

    DEFINITION_URL = DEF_URL_DELAY

    def __new__(cls, *args, **kwargs):
        return super().__new__(cls, *args, **kwargs)


CFunction.register_subclass(Delay)


class RateOf(CFunction):
    """Produces a SBML ``rateOf()`` function.

    Usually, it's preferable to use the :func:`rate_of` function.
    This class can be used if a *rateOf* function with a different name is
    needed.

    Examples:
        >>> from sympy.abc import a
        >>> my_rate_of = RateOf("my_rate_of")
        >>> my_rate_of(a)
        my_rate_of(a)
        >>> rate_of(a) == my_rate_of(a)
        True
        >>> rate_of(1)
        0
    """

    DEFINITION_URL = DEF_URL_RATE_OF

    def __new__(cls, *args, **kwargs):
        return super().__new__(cls, *args, **kwargs)

    @classmethod
    def eval(cls, x):
        if isinstance(x, Number):
            # the rate of a constant is 0
            return 0


CFunction.register_subclass(RateOf)

# SBML-defined functions

#: The SBML ``delay()`` function.
delay = Delay("delay")

#: The SBML ``rateOf()`` function.
rate_of = RateOf("rateOf")
