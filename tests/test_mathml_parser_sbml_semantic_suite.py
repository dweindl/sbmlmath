"""Test MathML parser on SBML semantic cases

(test suite at https://github.com/sbmlteam/sbml-test-suite/)
"""
import os
from pathlib import Path

import libsbml
import pytest

from sbmlmath import SBMLMathMLParser

sbml_test_suite_root = os.environ.get('SBML_TEST_SUITE_ROOT', '')
if not sbml_test_suite_root:
    pytest.skip("$SBML_TEST_SUITE_ROOT not set", allow_module_level=True)

cases_root = Path(sbml_test_suite_root, 'cases', 'semantic')
cases = sorted(cases_root.rglob("*-sbml-l3v2.xml"))
assert len(cases)
@pytest.mark.parametrize(
    ('sbml_file', ),
    [[file] for file in cases],
    ids=map(lambda x: x.stem, cases)
)
def test_sbml(sbml_file):
    print()
    print(sbml_file)

    # load file, try to parse all math elements
    sbml_reader = libsbml.SBMLReader()
    sbml_doc = sbml_reader.readSBMLFromFile(str(sbml_file))
    sbml_model = sbml_doc.getModel()

    parser = SBMLMathMLParser()
    for element in sbml_model.getListOfAllElements():
        if (get_math := getattr(element, 'getMath', None)) \
                and (mathml := libsbml.writeMathMLToString(get_math())):
            print(element.getId())
            print(mathml)
            try:
                sym = parser.parse_str(mathml)
                print(sym)
            except NotImplementedError as e:
                pytest.skip(str(e))
            print()
