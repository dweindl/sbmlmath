from typing import Union

import libsbml
import sympy as sp

from .mathml_parser import SBMLMathMLParser
from .mathml_printer import SBMLMathMLPrinter
from .species_symbol import SpeciesSymbol
from .csymbol import *
from .cfunction import *


__all__ = [
    "SBMLMathMLParser",
    "SBMLMathMLPrinter",
    "SpeciesSymbol",
    "TimeSymbol",
    "sympy_to_sbml_math",
    "sbml_math_to_sympy",
    *csymbol.__all__,
    *cfunction.__all__,
]


def sympy_to_sbml_math(sp_expr: sp.Expr) -> libsbml.ASTNode:
    """Convert sympy expression to SBML math ASTNode"""
    mathml = SBMLMathMLPrinter().doprint(sp_expr)

    if ast_node := libsbml.readMathMLFromString(mathml):
        return ast_node

    raise ValueError(
        f"Unknown error handling math expression:\n{sp_expr}\n" f"{mathml}"
    )


def sbml_math_to_sympy(
    sbml_obj: Union[libsbml.SBase, libsbml.ASTNode]
) -> sp.Expr:
    """Convert SBML MathML to sympy using the custom MathML parser"""
    ast_node = (
        sbml_obj
        if isinstance(sbml_obj, libsbml.ASTNode)
        else sbml_obj.getMath()
    )
    mathml = libsbml.writeMathMLToString(ast_node)
    return SBMLMathMLParser().parse_str(mathml)
