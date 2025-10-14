from math import fabs

import libsbml
from sympy import Rational

from sbmlmath import SBMLMathMLPrinter, SpeciesSymbol


def test_species_symbol_repr_type():
    sym = SpeciesSymbol("A", representation_type="sum")
    mathml = SBMLMathMLPrinter().doprint(sym)
    assert mathml == (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<math xmlns="http://www.w3.org/1998/Math/MathML" '
        'xmlns:multi="http://www.sbml.org/sbml/level3/version1/multi/version1">\n'
        '<ci multi:representationType="sum">A</ci>'
        "</math>"
    )


def test_species_symbol_spec_ref():
    sym = SpeciesSymbol("A", species_reference="ref_to_A")
    mathml = SBMLMathMLPrinter().doprint(sym)
    assert mathml == (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<math xmlns="http://www.w3.org/1998/Math/MathML" '
        'xmlns:multi="http://www.sbml.org/sbml/level3/version1/multi/version1">\n'
        '<ci multi:speciesReference="ref_to_A">A</ci>'
        "</math>"
    )


def test_print_large_rational():
    # too large for SBML int32 -> must be printed as float
    assert "rational" not in SBMLMathMLPrinter().doprint(Rational(1, 2**42))
    assert "rational" not in SBMLMathMLPrinter().doprint(Rational(2**42, 7))
    assert (
        fabs(
            libsbml.readMathMLFromString(
                SBMLMathMLPrinter().doprint(Rational(1, 2**42))
            ).getValue()
            - 1 / 2**42
        )
        < 1e-15
    )
