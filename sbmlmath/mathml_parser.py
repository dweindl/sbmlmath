"""SBML mathml to sympy."""
import contextlib
import operator as operators
from functools import reduce
from io import BytesIO

import sympy as sp
from lxml import etree
from pint import UnitRegistry
from sympy.logic.boolalg import Boolean, BooleanFalse, BooleanTrue

from .species_symbol import SpeciesSymbol

mathml_ns = "http://www.w3.org/1998/Math/MathML"
_ureg = UnitRegistry()
_ureg.Quantity.name = property(fget=lambda s: f"({s})")
_ureg.Quantity_sympy_ = lambda s: sp.sympify(f'{s.m}*{s.u:~}')

mathml_op_sympy_trigonometric = {
    f"{{{mathml_ns}}}sin": sp.sin,
    f"{{{mathml_ns}}}cos": sp.cos,
    f"{{{mathml_ns}}}tan": sp.tan,
    f"{{{mathml_ns}}}sec": sp.sec,
    f"{{{mathml_ns}}}csc": sp.csc,
    f"{{{mathml_ns}}}cot": sp.cot,
    f"{{{mathml_ns}}}sinh": sp.sinh,
    f"{{{mathml_ns}}}cosh": sp.cosh,
    f"{{{mathml_ns}}}tanh": sp.tanh,
    f"{{{mathml_ns}}}sech": sp.sech,
    f"{{{mathml_ns}}}csch": sp.csch,
    f"{{{mathml_ns}}}coth": sp.coth,
    f"{{{mathml_ns}}}arccos": sp.acos,
    f"{{{mathml_ns}}}arcsin": sp.asin,
    f"{{{mathml_ns}}}arctan": sp.atan,
    f"{{{mathml_ns}}}arcsec": sp.asec,
    f"{{{mathml_ns}}}arccsc": sp.acsc,
    f"{{{mathml_ns}}}arccot": sp.acot,
    f"{{{mathml_ns}}}arcsinh": sp.asinh,
    f"{{{mathml_ns}}}arccosh": sp.acosh,
    f"{{{mathml_ns}}}arctanh": sp.atanh,
    f"{{{mathml_ns}}}arcsech": sp.asech,
    f"{{{mathml_ns}}}arccsch": sp.acsch,
    f"{{{mathml_ns}}}arccoth": sp.acoth,
}
mathml_op_sympy_boolean = {
    f"{{{mathml_ns}}}and": sp.And,
    f"{{{mathml_ns}}}or": sp.Or,
    f"{{{mathml_ns}}}xor": sp.Xor,
}

mathml_op_sympy = {
    f"{{{mathml_ns}}}times":
        lambda *args: reduce(operators.mul, args, sp.Integer(1)),
    f"{{{mathml_ns}}}power": lambda base, exponent: base ** exponent,
    f"{{{mathml_ns}}}eq": sp.Equality,
    f"{{{mathml_ns}}}neq": sp.Unequality,
    f"{{{mathml_ns}}}lt": sp.StrictLessThan,
    f"{{{mathml_ns}}}gt": sp.StrictGreaterThan,
    f"{{{mathml_ns}}}geq": sp.GreaterThan,
    f"{{{mathml_ns}}}leq": sp.LessThan,
    f"{{{mathml_ns}}}max": sp.Max,
    f"{{{mathml_ns}}}min": sp.Min,
    f"{{{mathml_ns}}}abs": sp.Abs,
    f"{{{mathml_ns}}}exp": sp.exp,
    f"{{{mathml_ns}}}ceiling": sp.ceiling,
    f"{{{mathml_ns}}}floor": sp.floor,
    f"{{{mathml_ns}}}factorial": sp.factorial,
    f"{{{mathml_ns}}}ln": sp.log,
    f"{{{mathml_ns}}}not": sp.Not,
    f"{{{mathml_ns}}}rem": sp.Mod,
    f"{{{mathml_ns}}}implies": sp.Implies,
    **mathml_op_sympy_trigonometric,
    **mathml_op_sympy_boolean,
}

# unary functions
unary = {
    f"{{{mathml_ns}}}plus",
    f"{{{mathml_ns}}}minus",
    f"{{{mathml_ns}}}times",
    *mathml_op_sympy_boolean,
    f"{{{mathml_ns}}}abs",
    f"{{{mathml_ns}}}exp",
    f"{{{mathml_ns}}}ceiling",
    f"{{{mathml_ns}}}floor",
    f"{{{mathml_ns}}}factorial",
    f"{{{mathml_ns}}}ln",
    f"{{{mathml_ns}}}not",
    f"{{{mathml_ns}}}min",
    f"{{{mathml_ns}}}max",
    f"{{{mathml_ns}}}root",
    *mathml_op_sympy_trigonometric
}
# n-ary functions
n_ary = {
    f"{{{mathml_ns}}}times",
    f"{{{mathml_ns}}}plus",
    *mathml_op_sympy_boolean,
    f"{{{mathml_ns}}}lt",
    f"{{{mathml_ns}}}gt",
    f"{{{mathml_ns}}}geq",
    f"{{{mathml_ns}}}leq",
    f"{{{mathml_ns}}}eq",
    f"{{{mathml_ns}}}min",
    f"{{{mathml_ns}}}max",
}
# MathML-defined constants
constants = {
    f"{{{mathml_ns}}}exponentiale": sp.E,
    f"{{{mathml_ns}}}true": BooleanTrue(),
    f"{{{mathml_ns}}}false": BooleanFalse(),
    f"{{{mathml_ns}}}notanumber": sp.Float("nan"),
    f"{{{mathml_ns}}}pi": sp.pi,
    f"{{{mathml_ns}}}infinity": sp.Float("inf"),
}


class SBMLMathMLParser:
    """MathML parser for sympy, restricted to the SBML subset of MathML 2.0

    SBML spec:
    https://raw.githubusercontent.com/combine-org/combine-specifications/main/specifications/files/sbml.level-3.version-2.core.release-2.pdf
    section 3.4
    """

    def __init__(self, ureg: UnitRegistry = None):
        self.ureg = ureg or _ureg or UnitRegistry()
        # TODO configurable version
        #  TODO {prefix=>url}
        self.sbml_core_ns = \
            'http://www.sbml.org/sbml/level3/version2/core'
        self.sbml_multi_ns = \
            'http://www.sbml.org/sbml/level3/version1/multi/version1'

    def parse_file(self, file_like) -> sp.Expr:
        element_tree = etree.parse(file_like)
        for element in element_tree.iter():
            if element.tag == f"{{{mathml_ns}}}math":
                continue

            return self._parse_element(element)

    def parse_str(self, mathml: str):
        # (fragile) workaround for libsbml dropping xmlns declarations for
        #  namespaces other than 'sbml'
        if "multi:" in mathml and 'xmlns:multi' not in mathml:
            math_element = '<math xmlns="http://www.w3.org/1998/Math/MathML"'
            mathml = mathml.replace(
                math_element,
                f'{math_element} xmlns:multi="{self.sbml_multi_ns}"'
            )
        # end

        return self.parse_file(file_like=BytesIO(mathml.encode()))

    def _parse_element(self, element: etree._Element) -> sp.Expr:
        mathml_prefix = f"{{{mathml_ns}}}"
        if not element.tag.startswith(mathml_prefix):
            raise AssertionError(element.tag)

        stripped_tag = element.tag[len(mathml_prefix):]

        handler = f"handle_{stripped_tag}"
        if handler := getattr(self, handler, None):
            try:
                return handler(element)
            except NotImplementedError:
                raise
            except Exception as e:
                raise ValueError(
                    f"Failed parsing:\n{etree.tostring(element).decode()}"
                ) from e
        with contextlib.suppress(KeyError):
            return constants[element.tag]

        raise NotImplementedError(f"Unhandled element: {element.tag}.")

    def handle_apply(self, element: etree._Element) -> sp.Expr:
        """Handle <apply>"""
        operator, *operands = element
        sym_operands = list(map(self._parse_element, operands))

        # TODO cleanup; doesn't check properly if compatible with 2 args
        if operator.tag not in (f"{{{mathml_ns}}}csymbol",
                                f"{{{mathml_ns}}}ci") \
                and (len(operands) == 1 and operator.tag not in unary
                     or len(operands) > 2 and operator.tag not in n_ary):
            raise AssertionError(
                f"Unknown arity for {operator.tag} ({operands}"
            )

        if operator.tag.startswith(f"{{{mathml_ns}}}"):
            stripped_tag = operator.tag[len(f"{{{mathml_ns}}}"):]
            if len(operands) == 1 \
                    and stripped_tag in {'plus', 'times', 'and', 'or',
                                         'xor', 'min', 'max'}:
                return sym_operands[0]

            if stripped_tag in ("gt", "lt", "leq", "geq", "eq") \
                    and len(operands) >= 3:
                # n-ary relational operators:
                #  a < b < c cannot directory be represented in sympy.
                #  either change to `a < b and b < c`, to be sympy-evaluatable,
                #  or to Function('MathML_Lt')(a, b, c), which will cycle
                #  (although potentially collide with other functions with
                #  that name), but which cannot be evaluated in sympy.
                #  The Function-approach won't work when used in piecewise
                #  -> "Second argument must be a Boolean, not `lt`"
                #  Therefore, chain expressions with `and`.
                sym_operator = mathml_op_sympy[operator.tag]
                expr = True
                for i in range(len(sym_operands) - 1):
                    expr = sp.And(
                        expr, sym_operator(sym_operands[i],
                                           sym_operands[i + 1])
                    )
                return expr

        # TODO: need to handle boolean->{int,float} conversion via
        #  `Piecewise((1, expr),(0,True))`
        #  {int,float} -> bool
        #  `Piecewise((True, expr != 0),(False,True))`
        #  as sympy doesn't do that automatically
        if operator.tag not in mathml_op_sympy_boolean:
            sym_operands = list(map(_bool2num, sym_operands))

        with contextlib.suppress(KeyError):
            return mathml_op_sympy[operator.tag](*sym_operands)

        if operator.tag == f"{{{mathml_ns}}}divide":
            assert len(sym_operands) == 2
            return sym_operands[0] / sym_operands[1]

        if operator.tag == f"{{{mathml_ns}}}plus":
            # note: unary version is handled above
            # return sp.Add(*sym_operands)
            return reduce(operators.add, sym_operands, sp.Integer(0))

        if operator.tag == f"{{{mathml_ns}}}minus":
            if len(sym_operands) == 2:
                return sym_operands[0] - sym_operands[1]
            if len(sym_operands) == 1:
                return -sym_operands[0]
            raise AssertionError(list(element))

        if operator.tag == f"{{{mathml_ns}}}root":
            assert len(sym_operands) in {1, 2}
            if len(sym_operands) == 1:
                # defaults to sqrt
                degree = 2
            else:
                degree = sym_operands[0]
                assert operands[0].tag == f"{{{mathml_ns}}}degree"

            return sym_operands[-1] ** (1 / degree)

        if operator.tag == f"{{{mathml_ns}}}log":
            assert len(operands) == 2
            assert operands[0].tag == f"{{{mathml_ns}}}logbase"
            assert len(operands[0]) == 1
            base, x = sym_operands
            # won't cycle - will be transformed to ``log(x)/log(base)``
            return sp.log(x, base)

        if operator.tag == f"{{{mathml_ns}}}quotient":
            # there is no direct correspondence for integer division in sympy,
            # so we use modulo instead. this won't cycle.
            # a // b = (a - a mod b) / b
            assert len(operands) == 2
            a, b = sym_operands
            return (a - a % b) / b

        if operator.tag == f"{{{mathml_ns}}}csymbol":
            # TODO store definitionURL somewhere?
            # TODO need to be able to distinguish between lambdas referenced
            #  through ci and functions from csymbols
            assert operator.attrib['encoding'] == "text"
            return sp.Function(operator.text.strip())(*sym_operands)

        if operator.tag == f"{{{mathml_ns}}}ci":
            assert not operator.attrib
            return sp.Function(operator.text.strip())(*sym_operands)

        raise NotImplementedError(f"Unsupported operator {operator.tag}.")

    def handle_ci(self, element: etree._Element) -> sp.Expr:
        """Handle identifiers."""
        handled_attrs = {
            # TODO: remove after fixing xmlns in model
            'multi:representationType',
            'multi:speciesReference',
            f'{{{self.sbml_multi_ns}}}representationType',
            f'{{{self.sbml_multi_ns}}}speciesReference',
        }
        if unhandled_attrs := (set(element.attrib.keys()) - handled_attrs):
            raise NotImplementedError(
                f"Unhandled <ci> attributes: {unhandled_attrs}")

        representation_type = element.attrib.get(
            f'{{{self.sbml_multi_ns}}}representationType', None) \
                              or element.attrib.get('multi:representationType', None)
        species_reference = element.attrib.get(
            f'{{{self.sbml_multi_ns}}}speciesReference', None) \
                            or element.attrib.get('multi:speciesReference',
                                                  None)
        symbol_name = element.text.strip()
        if representation_type or species_reference:
            return SpeciesSymbol(
                name=symbol_name,
                representation_type=representation_type,
                species_reference=species_reference,
            )
        return sp.Symbol(symbol_name)

    def handle_cn(self, element: etree._Element) -> sp.Expr:
        """Handle numbers."""
        handled_attrs = {
            'type',
            f'{{{self.sbml_core_ns}}}units',
        }
        if unhandled_attrs := (set(element.attrib.keys()) - handled_attrs):
            raise NotImplementedError(
                f"Unhandled <cn> attributes: {unhandled_attrs}")
        dtype = element.attrib.get('type', 'real')
        converter = {
            'real':
                lambda element: sp.Float(element.text),
            'integer':
                lambda element: sp.Integer(element.text),
            'rational':
                lambda element: sp.Rational(element.text, element[0].tail),
            'e-notation':
            # this won't cycle. we don't have a corresponding
            #  representation in sympy
                lambda element: sp.Float(
                    float(element.text) * 10 ** int(element[0].tail)
                ),
        }.get(dtype)
        if not converter:
            raise NotImplementedError(f"Unhandled type: {dtype}")
        obj = converter(element)

        if units := element.attrib.get(f'{{{self.sbml_core_ns}}}units', None):
            if units not in self.ureg:
                # TODO fixme: replace rhs by base units
                #  this requires access to the underlying SBML model to access
                #  unit definitions. they should be parsed during __init__.
                #  base units defined in SBML can be handled without a model,
                #  as they are not allowed to be redefined (are they?).
                #  should start from an empty UnitRegistry, as sbml could
                #  redefine any (non-base?)unit to whatever.
                self.ureg.define(f"{units} = {units}")
            # TODO pint.Quantitiy causes issues with sympy functions:
            #  https://docs.sympy.org/latest/explanation/active-deprecations.html#non-expr-args-deprecated
            return self.ureg.Quantity(obj, units)
        return obj

    def handle_piecewise(self, element: etree._Element) -> sp.Expr:
        expr_cond_pairs = []
        for e in element:
            # TODO: cannot currently handle functions as condition-arguments.
            #   they need to be derived sympy.BooleanFunction
            if e.tag == f"{{{mathml_ns}}}piece":
                assert len(e) == 2
                cond = self._parse_element(e[1])
                if not isinstance(cond, Boolean):
                    raise NotImplementedError(
                        "Cannot handle non-boolean piecewise conditions: "
                        f"{cond}"
                    )
                expr_cond_pairs.append((self._parse_element(e[0]), cond), )
            elif e.tag == f"{{{mathml_ns}}}otherwise":
                # may occur only as last condition
                assert e is element[-1]
                assert len(e) == 1
                expr_cond_pairs.append((self._parse_element(e[0]), True), )
            else:
                raise AssertionError(e.tag)
        return sp.Piecewise(*expr_cond_pairs)

    def handle_lambda(self, element: etree._Element) -> sp.Expr:
        # collect arguments / bound variables
        args = []
        for e in element[:-1]:
            assert e.tag == f"{{{mathml_ns}}}bvar"
            assert len(e) == 1
            args.append(self._parse_element(e[0]))

        rhs = self._parse_element(element[-1])
        return sp.Lambda(tuple(args), rhs)

    def handle_degree(self, element: etree._Element) -> sp.Expr:
        assert len(element) == 1
        return self._parse_element(element[0])

    def handle_logbase(self, element: etree._Element) -> sp.Expr:
        assert len(element) == 1
        return self._parse_element(element[0])

    def handle_csymbol(self, element: etree._Element) -> sp.Expr:
        assert element.attrib['encoding'] == "text"
        return sp.Dummy(element.text.strip())


def _bool2num(x):
    if isinstance(x, BooleanFalse):
        return sp.Integer(0)
    if isinstance(x, BooleanTrue):
        return sp.Integer(1)
    return x
