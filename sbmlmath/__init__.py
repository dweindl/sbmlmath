from typing import Union

import libsbml
import sympy as sp

from .cfunction import *
from .csymbol import *
from .mathml_parser import SBMLMathMLParser
from .mathml_printer import SBMLMathMLPrinter
from .species_symbol import SpeciesSymbol

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
    """Convert sympy expression to SBML math ASTNode.

    This function takes a SymPy expression and converts it to an SBML math
    ASTNode.

    Args:
        sp_expr: The SymPy expression to be converted.

    Returns:
        The resulting SBML math ASTNode.

    Raises:
        ValueError:
            If there is an error in converting the math expression.
    """
    mathml = SBMLMathMLPrinter().doprint(sp_expr)

    if ast_node := libsbml.readMathMLFromString(mathml):
        return ast_node

    raise ValueError(
        f"Unknown error handling math expression:\n{sp_expr}\n" f"{mathml}"
    )


def sbml_math_to_sympy(
    sbml_obj: Union[libsbml.SBase, libsbml.ASTNode]
) -> sp.Expr:
    """Convert SBML MathML to sympy expression.

    Conversion is done using the default settings of :class:`SBMLMathMLParser`.

    Args:
        sbml_obj:
            The SBML object to be converted.
            (Either directly the ASTNode or the surrounding SBase object).
    Returns:
        The resulting sympy expression.
    """
    ast_node = (
        sbml_obj
        if isinstance(sbml_obj, libsbml.ASTNode)
        else sbml_obj.getMath()
    )
    mathml = libsbml.writeMathMLToString(ast_node)
    return SBMLMathMLParser().parse_str(mathml)
