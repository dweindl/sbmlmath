"""Convenience functions for libsbml core"""
from numbers import Number

import sympy as sp
from sympy.printing.mathml import MathMLContentPrinter

from .species_symbol import SpeciesSymbol
from .csymbol import CSymbol


__all__ = ["SBMLMathMLPrinter"]


class SBMLMathMLPrinter(MathMLContentPrinter):
    """MathML printer

    * assumes all constants are dimensionless
    """

    def __init__(
        self,
        *args,
        literals_dimensionless=True,
        sbml_level: int = 3,
        sbml_version: int = 2,
        **kwargs,
    ):
        """Construct.

        :param literals_dimensionless:
            Assume numeric literals are dimensionless.
        """
        super().__init__(*args, **kwargs)

        self.mathml_ns = 'xmlns="http://www.w3.org/1998/Math/MathML"'
        self.sbml_ns = f'xmlns:sbml="http://www.sbml.org/sbml/level{sbml_level}/version{sbml_version}/core"'
        # note: so far, there is no L3V2-multi
        self.multi_ns = f'xmlns:multi="http://www.sbml.org/sbml/level{sbml_level}/version1/multi/version1"'
        self.literals_dimensionless = literals_dimensionless

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
            ci.setAttribute("multi:representationType", sym.representation_type)
        if sym.species_reference:
            ci.setAttribute("multi:speciesReference", sym.species_reference)
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

        prolog = (
            '<?xml version="1.0" encoding="UTF-8"?>\n' if with_prolog else ""
        )

        sbml_ns = f" {self.sbml_ns}" if " sbml:" in mathml else ""
        multi_ns = f" {self.multi_ns}" if " multi:" in mathml else ""
        return (
            f"{prolog}<math {self.mathml_ns}{sbml_ns}{multi_ns}>\n"
            f"{mathml}</math>"
        )

    def _print_Number(self, e):
        # only try printing as int if it fits int32
        if isinstance(e, int) and e < 2**31 and e >= -(2**31):
            res = self._print_int(e)
        else:
            res = super()._print_Number(e)

        if self.literals_dimensionless:
            res.setAttribute("sbml:units", "dimensionless")
        return res

    def _print_Rational(self, e):
        if e.q == 1:
            # don't divide by one
            return self._print_int(e.p)

        res = self.dom.createElement("cn")
        res.setAttribute("type", "rational")
        res.appendChild(self.dom.createTextNode(f"{e.p} <sep/> {e.q}"))

        if self.literals_dimensionless:
            res.setAttribute("sbml:units", "dimensionless")
        return res

    def _print_int(self, e):
        if e >= 2**31 or e < -(2**31):
            # avoid int32 under/overflow in libsbml and print as float
            return self._print_Number(e)
        res = super()._print_int(e)
        res.setAttribute("type", "integer")
        if self.literals_dimensionless:
            res.setAttribute("sbml:units", "dimensionless")
        return res

    def _print_Float(self, e):
        res = super()._print_Float(e)
        if self.literals_dimensionless:
            res.setAttribute("sbml:units", "dimensionless")
        return res

    def _print_One(self, e):
        res = self._print_int(e)
        if self.literals_dimensionless:
            res.setAttribute("sbml:units", "dimensionless")
        return res

    def _print_Quantity(self, e):
        res = self._print(e.m)
        if isinstance(e.m, Number):
            # TODO this unit may not exist and might have to be created
            # TODO if Quantities are used in sympy expressions, they might
            #  units might get shuffled around and end up <apply>. In this case
            #  we skip settings units for now.
            res.setAttribute("sbml:units", str(e.u))
        return res

    def _print_CSymbol(self, e: CSymbol):
        dom_element = self.dom.createElement("csymbol")
        dom_element.appendChild(self.dom.createTextNode(str(e)))
        if e.definition_url:
            dom_element.setAttribute("definitionURL", e.definition_url)
        if e.encoding:
            dom_element.setAttribute("encoding", e.encoding)

        return dom_element

    def _print_Function(self, e):
        if hasattr(e, "definition_url"):
            return self._print_CFunction(e)
        return super()._print_Function(e)

    def _print_CFunction(self, e):
        dom_element = self.dom.createElement("apply")
        csymbol = self.dom.createElement("csymbol")
        csymbol.appendChild(self.dom.createTextNode(e.name))

        if e.definition_url:
            csymbol.setAttribute("definitionURL", e.definition_url)
        if e.encoding:
            csymbol.setAttribute("encoding", e.encoding)
        dom_element.appendChild(csymbol)
        for arg in e.args:
            dom_element.appendChild(self._print(arg))

        return dom_element
