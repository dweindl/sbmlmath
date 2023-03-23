"""Convenience functions for libsbml core"""
from numbers import Number

import sympy as sp
from sympy.printing.mathml import MathMLContentPrinter

from .species_symbol import SpeciesSymbol


class MyMathMLContentPrinter(MathMLContentPrinter):
    """MathML printer

    * assumes all constants are dimensionless
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # TODO don't hardcode version / level
        self.mathml_ns = 'xmlns="http://www.w3.org/1998/Math/MathML"'
        self.sbml_ns = 'xmlns:sbml="http://www.sbml.org/sbml/level3/version2/core"'
        self.multi_ns = 'xmlns:multi="http://www.sbml.org/sbml/level3/version1/multi/version1"'

    def _print_Symbol(self, sym):
        """
        Print Symbol (<ci>)

        Skip MathML presentation layer, which is not part of the SBML MathML
        subset.
        """
        ci = self.dom.createElement(self.mathml_tag(sym))
        ci.appendChild(self.dom.createTextNode(sym.name))
        return ci

    def _print_SpeciesSymbol(self, sym: SpeciesSymbol):
        ci = self._print_Symbol(sym)
        if sym.representation_type:
            # TODO should <math> should include multi-ns
            ci.setAttribute("multi:representationType",
                            sym.representation_type)
        if sym.species_reference:
            ci.setAttribute("multi:speciesReference",
                            sym.species_reference)
        return ci

    def doprint(self, expr, with_prolog=True, with_math=True):
        if isinstance(expr, float):
            expr = sp.Float(expr)
        try:
            mathml = super().doprint(expr)
        except Exception as e:
            raise ValueError(f"MathML printing failed for {expr}") from e

        if not with_math:
            return mathml

        prolog = '<?xml version="1.0" encoding="UTF-8"?>\n' \
            if with_prolog else ""

        # TODO: only include sbml_ns / multi_ns where required
        return (
            f'{prolog}<math {self.mathml_ns} {self.sbml_ns} {self.multi_ns}>\n'
            f'{mathml}</math>'
        )

    def _print_Number(self, e):
        res = super()._print_int(e)
        res.setAttribute('sbml:units', 'dimensionless')
        return res

    def _print_Rational(self, e):
        res = super()._print_int(e)
        res.setAttribute('sbml:units', 'dimensionless')
        return res

    def _print_int(self, e):
        res = super()._print_int(e)
        res.setAttribute('sbml:units', 'dimensionless')
        return res

    def _print_Float(self, e):
        res = super()._print_Float(e)
        res.setAttribute('sbml:units', 'dimensionless')
        return res

    def _print_One(self, e):
        res = super()._print_int(e)
        res.setAttribute('sbml:units', 'dimensionless')
        return res

    def _print_Quantity(self, e):
        res = self._print(e.m)
        if isinstance(e.m, Number):
            # TODO this unit may not exist and might have to be created
            # TODO if Quantities are used in sympy expressions, they might
            #  units might get shuffled around and end up <apply>. In this case
            #  we skip settings units for now.
            res.setAttribute('sbml:units', str(e.u))
        return res
