from sbmlmath import SpeciesSymbol, MyMathMLContentPrinter


def test_species_symbol_repr_type():
    sym = SpeciesSymbol("A", representation_type="sum")
    mathml = MyMathMLContentPrinter().doprint(sym)
    assert mathml == (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<math xmlns="http://www.w3.org/1998/Math/MathML" '
        'xmlns:sbml="http://www.sbml.org/sbml/level3/version2/core" '
        'xmlns:multi="http://www.sbml.org/sbml/level3/version1/multi/version1">\n'
        '<ci multi:representationType="sum">A</ci>'
        '</math>'
    )


def test_species_symbol_spec_ref():
    sym = SpeciesSymbol("A", species_reference="ref_to_A")
    mathml = MyMathMLContentPrinter().doprint(sym)
    assert mathml == (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<math xmlns="http://www.w3.org/1998/Math/MathML" '
        'xmlns:sbml="http://www.sbml.org/sbml/level3/version2/core" '
        'xmlns:multi="http://www.sbml.org/sbml/level3/version1/multi/version1">\n'
        '<ci multi:speciesReference="ref_to_A">A</ci>'
        '</math>'
    )

