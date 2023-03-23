"""SBML MathML related functionality"""
from typing import Literal, Optional

import sympy as sp


class SpeciesSymbol(sp.Dummy):
    """
    Represents a <ci> element containing a species.

    Represents e.g.:
    ``<ci multi:representationType="sum"> bla </ci>``
    ``<ci multi:speciesReference="refS"> S </ci>``
    (see SBML multi specs 3.26)

    Subclassed from sympy.Dummy to avoid caching issues, due to using the same
    name but with different meanings.

    representation_type: SBML-multi spec 3.26.2
    species_reference: SBML-multi spec 3.26.1. ID of a species reference in the
        same reaction.
    """
    _cache = {}

    def __new__(
            cls, *args,
            representation_type:
            Optional[Literal['sum', 'numericValue']] = None,
            species_reference: str = None,
            **kwargs
    ):
        # Cache instances.
        # If not done: (SpeciesSymbol("A") == SpeciesSymbol("A")) == False
        if not (name := kwargs.get("name")):
            name = args[0]
        cache_key = (name, representation_type, species_reference)
        if cached := cls._cache.get(cache_key):
            return cached

        obj = super().__new__(cls, *args, **kwargs)
        obj.representation_type = representation_type
        obj.species_reference = species_reference

        cls._cache[cache_key] = obj

        return obj

    def __repr__(self):
        rt = f"representation_type={self.representation_type},"\
            if self.representation_type else ""
        sr = f"species_reference={self.species_reference}," \
            if self.species_reference else ""

        return f"<{self.name}({rt}{sr})>"
