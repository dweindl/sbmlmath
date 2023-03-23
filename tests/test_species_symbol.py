import libsbml
import pytest
import sympy as sp
from sbmlmath import *


def test_species_symbol_equality():
    sym1 = SpeciesSymbol("A", representation_type="sum")
    sym2 = SpeciesSymbol("A", species_reference="ref_to_A")

    # ensure they are not considered equal
    assert sym1 is not sym2
    assert sym1 != sym2

    # Test caching works
    assert SpeciesSymbol("A", representation_type="sum") \
           == SpeciesSymbol("A", representation_type="sum")
    assert SpeciesSymbol("A", representation_type="sum") \
           is SpeciesSymbol("A", representation_type="sum")
    assert SpeciesSymbol("A") is SpeciesSymbol("A")


def test_species_symbol_operations():
    sym1 = SpeciesSymbol("A", representation_type="sum")
    sym2 = SpeciesSymbol("A", species_reference="ref_to_A")

    expr = sym1 + sym2
    mathml = MyMathMLContentPrinter().doprint(expr)
    assert mathml == (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<math xmlns="http://www.w3.org/1998/Math/MathML" '
        'xmlns:sbml="http://www.sbml.org/sbml/level3/version2/core" '
        'xmlns:multi="http://www.sbml.org/sbml/level3/version1/multi/version1">\n'
        '<apply><plus/><ci multi:representationType="sum">A</ci>'
        '<ci multi:speciesReference="ref_to_A">A</ci></apply>'
        '</math>'
    )

    expr = sym1 * sym2
    mathml = MyMathMLContentPrinter().doprint(expr)
    assert mathml == (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<math xmlns="http://www.w3.org/1998/Math/MathML" '
        'xmlns:sbml="http://www.sbml.org/sbml/level3/version2/core" '
        'xmlns:multi="http://www.sbml.org/sbml/level3/version1/multi/version1">\n'
        '<apply><times/><ci multi:representationType="sum">A</ci>'
        '<ci multi:speciesReference="ref_to_A">A</ci></apply>'
        '</math>'
    )

    expr = sym1 + sym1 + sym2 * sym2
    mathml = MyMathMLContentPrinter().doprint(expr)
    assert mathml == (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<math xmlns="http://www.w3.org/1998/Math/MathML" '
        'xmlns:sbml="http://www.sbml.org/sbml/level3/version2/core" '
        'xmlns:multi="http://www.sbml.org/sbml/level3/version1/multi/version1">\n'
        '<apply><plus/><apply><times/><cn sbml:units="dimensionless">2</cn>'
        '<ci multi:representationType="sum">A</ci></apply>'
        '<apply><power/><ci multi:speciesReference="ref_to_A">A</ci>'
        '<cn sbml:units="dimensionless">2</cn></apply></apply>'
        '</math>'
    )

    # check subs() works
    assert (-1 + sym1).subs(sym1, 1) == 0

    # test mathml -> sympy
    mathml_exp = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<math xmlns="http://www.w3.org/1998/Math/MathML" '
        'xmlns:sbml="http://www.sbml.org/sbml/level3/version2/core" '
        'xmlns:multi="http://www.sbml.org/sbml/level3/version1/multi/version1">\n'
        '<apply><plus/><apply><times/><cn sbml:units="dimensionless">2</cn>'
        '<ci multi:representationType="sum">A</ci></apply>'
        '<apply><power/><ci multi:speciesReference="ref_to_A">A</ci>'
        '<cn sbml:units="dimensionless">2</cn></apply></apply>'
        '</math>'
    )
    sym_expr = SBMLMathMLParser().parse_str(mathml_exp)
    mathml_act = MyMathMLContentPrinter().doprint(sym_expr)

    # not an exact match, but close enough, for now
    #  TODO - some term re-ordering occurs
    #  TODO - integer / double handling is not happening
    assert mathml_act == (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<math xmlns="http://www.w3.org/1998/Math/MathML" '
        'xmlns:sbml="http://www.sbml.org/sbml/level3/version2/core" '
        'xmlns:multi="http://www.sbml.org/sbml/level3/version1/multi/version1">\n'
        '<apply><plus/><apply><power/>'
        '<ci multi:speciesReference="ref_to_A">A</ci>'
        '<cn sbml:units="dimensionless">2.0</cn></apply>'
        '<apply><times/><cn sbml:units="dimensionless">2.0</cn>'
        '<ci multi:representationType="sum">A</ci></apply></apply></math>'
    )

