"""SBML mathml to sympy."""

import contextlib
import operator as operators
from functools import reduce
from io import BytesIO
from typing import Union

import sympy as sp
from lxml import etree
from pint import UnitRegistry
from sympy import Piecewise
from sympy.logic.boolalg import (
    Boolean,
    BooleanFalse,
    BooleanTrue,
)

from . import _DEFAULT_SBML_LEVEL, _DEFAULT_SBML_VERSION
from .cfunction import CFunction
from .csymbol import CSymbol
from .species_symbol import SpeciesSymbol

__all__ = ["SBMLMathMLParser"]


mathml_ns = "http://www.w3.org/1998/Math/MathML"
# Create a default unit registry to be used if none is provided to SBMLMathMLParser.__init__.
#  Depending on the usage pattern, constructing a new UnitRegistry for each SBMLMathMLParser might be rather slow.
_ureg = UnitRegistry()
_ureg.Quantity.name = property(fget=lambda s: f"({s})")
_ureg.Quantity_sympy_ = lambda s: sp.sympify(f"{s.m}*{s.u:~}")


# some operator implementations to handle `evaluate`
#  *and* be compatible with non Expr operands
# (non-Expr is deprecated for Add, Mul, Pow, ...)
def _divide(*args, evaluate: bool = False):
    with sp.evaluate(evaluate):
        return operators.truediv(*args)


def _mul(*args, evaluate: bool = False):
    with sp.evaluate(evaluate):
        if len(args) >= 2:
            return reduce(operators.mul, args[1:], args[0])
        if len(args) == 1:
            return args[0]
        return sp.Integer(1)


def _pow(base, exponent, evaluate: bool = False):
    with sp.evaluate(evaluate):
        return base**exponent


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
    f"{{{mathml_ns}}}and": lambda *args, **kwargs: sp.And(*args, **kwargs)
    if kwargs.get("evaluate", False)
    else sp.And(*map(_num2bool, args), **kwargs),
    f"{{{mathml_ns}}}or": lambda *args, **kwargs: sp.Or(*args, **kwargs)
    if kwargs.get("evaluate", False)
    else sp.Or(*map(_num2bool, args), **kwargs),
    f"{{{mathml_ns}}}xor": lambda *args, **kwargs: sp.Xor(*args, **kwargs)
    if kwargs.get("evaluate", False)
    else sp.Xor(*map(_num2bool, args), **kwargs),
    f"{{{mathml_ns}}}implies": sp.Implies,
}

mathml_op_sympy = {
    # Using non-Expr arguments in Mul and Pow is deprecated
    #  and we might use pint.Quantitity, so we use operator.mul
    f"{{{mathml_ns}}}times": _mul,
    f"{{{mathml_ns}}}divide": _divide,
    f"{{{mathml_ns}}}power": _pow,
    f"{{{mathml_ns}}}eq": lambda *args, **kwargs: sp.Equality(*args, **kwargs),
    f"{{{mathml_ns}}}neq": lambda *args, **kwargs: sp.Unequality(
        *args, **kwargs
    ),
    f"{{{mathml_ns}}}lt": lambda *args, **kwargs: sp.StrictLessThan(
        *args, **kwargs
    ),
    f"{{{mathml_ns}}}gt": lambda *args, **kwargs: sp.StrictGreaterThan(
        *args, **kwargs
    ),
    f"{{{mathml_ns}}}geq": lambda *args, **kwargs: sp.GreaterThan(
        *args, **kwargs
    ),
    f"{{{mathml_ns}}}leq": lambda *args, **kwargs: sp.LessThan(
        *args, **kwargs
    ),
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
    *mathml_op_sympy_trigonometric,
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
    """MathML parser for sympy.

    Parses the SBML subset of MathML 2.0.

    For details, see SBML spec section 3.4:
    https://raw.githubusercontent.com/combine-org/combine-specifications/main/specifications/files/sbml.level-3.version-2.core.release-2.pdf.

    See also: `MathML 2.0 specification <https://www.w3.org/TR/MathML2/>`_.

    :param sbml_level: SBML level.
        Note that SBML level < 3 has not been thoroughly tested.
    :param sbml_version: SBML version.
    :param ureg:
        Optional :class:`pint.UnitRegistry` to use for unit conversion.
    :param floats_as_rationals:
        Whether to convert floats to :class:`sympy.Rational`.
        Improves precision.
    :param ignore_units:
        Whether to ignore units.
        If ``True``, all units are ignored and all numbers are converted to
        plain numbers.
        If ``False``, all math elements with units are converted to
        :class:`pint.Quantity` objects.
    :param symbol_kwargs:
        Additional keyword arguments for constructing :class:`sympy.Symbol`.
        For example, for passing custom assumptions such as ``real=True``.
    """

    def __init__(
        self,
        sbml_level: Union[int, str] = _DEFAULT_SBML_LEVEL,
        sbml_version: Union[int, str] = _DEFAULT_SBML_VERSION,
        ureg: UnitRegistry = None,
        floats_as_rationals=True,
        ignore_units=False,
        symbol_kwargs=None,
        evaluate=False,
    ):
        """Constructor"""
        self.ureg = ureg or _ureg or UnitRegistry()
        self.sbml_core_ns = f"http://www.sbml.org/sbml/level{sbml_level}/version{sbml_version}/core"
        #  TODO {prefix=>url}
        self.sbml_multi_ns = (
            # L3V2 doesn't work
            f"http://www.sbml.org/sbml/level{sbml_level}/version1/multi/version1"
        )
        self.floats_as_rationals = floats_as_rationals
        self.ignore_units = ignore_units
        self.symbol_kwargs = (
            {} if symbol_kwargs is None else symbol_kwargs.copy()
        )
        self.evaluate = evaluate

    def parse_file(self, file_like) -> sp.Expr:
        """Parse a file-like object containing MathML.

        :param file_like:
            File-like object (file, filename, ...) containing MathML.
            Expected to contain the XML prolog ``<?xml [...]?>``
            and the MathML ``math`` element.
        :return: The sympy representation of the MathML expression.
        """
        # Using `lxml` to parse untrusted data is known to be vulnerable to XML
        #  attacks
        element_tree = etree.parse(file_like)  # noqa S320
        for element in element_tree.iter():
            if element.tag == f"{{{mathml_ns}}}math":
                continue

            return self._parse_element(element)

    def parse_str(self, mathml: str):
        """Parse a string containing MathML.

        :param mathml:
            MathML string. Expected to contain the XML prolog ``<?xml [...]?>``
            and the MathML ``math`` element.
        :return: The sympy representation of the MathML expression.
        """
        # (fragile) workaround for libsbml<5.20.0 dropping xmlns declarations
        #  for namespaces other than 'sbml'
        if "multi:" in mathml and "xmlns:multi" not in mathml:
            math_element = '<math xmlns="http://www.w3.org/1998/Math/MathML"'
            mathml = mathml.replace(
                math_element,
                f'{math_element} xmlns:multi="{self.sbml_multi_ns}"',
            )
        # end

        return self.parse_file(file_like=BytesIO(mathml.encode()))

    def _parse_element(self, element: etree._Element) -> sp.Expr:
        mathml_prefix = f"{{{mathml_ns}}}"
        if not element.tag.startswith(mathml_prefix):
            raise AssertionError(element.tag)

        stripped_tag = element.tag[len(mathml_prefix) :]

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

    def handle_apply(self, element: etree._Element) -> sp.Expr:  # noqa C901
        """Handle <apply>"""
        operator, *operands = element
        sym_operands = list(map(self._parse_element, operands))

        # TODO cleanup; doesn't check properly if compatible with 2 args
        if operator.tag not in (
            f"{{{mathml_ns}}}csymbol",
            f"{{{mathml_ns}}}ci",
        ) and (
            len(operands) == 1
            and operator.tag not in unary
            or len(operands) > 2
            and operator.tag not in n_ary
        ):
            raise AssertionError(
                f"Unknown arity for {operator.tag} ({operands}"
            )

        if operator.tag.startswith(f"{{{mathml_ns}}}"):
            stripped_tag = operator.tag[len(f"{{{mathml_ns}}}") :]
            if len(operands) == 1 and stripped_tag in {
                "plus",
                "times",
                "and",
                "or",
                "xor",
                "min",
                "max",
            }:
                return sym_operands[0]

            if (
                stripped_tag in ("gt", "lt", "leq", "geq", "eq")
                and len(operands) >= 3
            ):
                # n-ary relational operators:
                #  a < b < c cannot directly be represented in sympy.
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
                        expr,
                        sym_operator(
                            sym_operands[i],
                            sym_operands[i + 1],
                            evaluate=self.evaluate,
                        ),
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
            return mathml_op_sympy[operator.tag](
                *sym_operands, evaluate=self.evaluate
            )

        if operator.tag == f"{{{mathml_ns}}}plus":
            with sp.evaluate(self.evaluate):
                if len(sym_operands) >= 2:
                    return reduce(
                        operators.add, sym_operands[1:], sym_operands[0]
                    )
                if len(sym_operands) == 1:
                    return sym_operands[0]
                if len(sym_operands) == 0:
                    return sp.Integer(0)

        if operator.tag == f"{{{mathml_ns}}}minus":
            with sp.evaluate(self.evaluate):
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

            with sp.evaluate(self.evaluate):
                return sym_operands[-1] ** (1 / degree)

        if operator.tag == f"{{{mathml_ns}}}log":
            assert len(operands) == 2
            assert operands[0].tag == f"{{{mathml_ns}}}logbase"
            assert len(operands[0]) == 1
            base, x = sym_operands
            # won't cycle - will be transformed to ``log(x)/log(base)``
            return sp.log(x, base, evaluate=self.evaluate)

        if operator.tag == f"{{{mathml_ns}}}quotient":
            # there is no direct correspondence for integer division in sympy,
            # so we use modulo instead. this won't cycle.
            # a // b = (a - a mod b) / b
            assert len(operands) == 2
            a, b = sym_operands
            with sp.evaluate(self.evaluate):
                return (a - a % b) / b

        name = self.preprocess_symbol_name(operator.text.strip(), operator)

        if operator.tag == f"{{{mathml_ns}}}csymbol":
            # examples: rateOf, delay, distributions from distrib package
            assert operator.attrib["encoding"] == "text"
            return CFunction(
                name,
                definition_url=operator.attrib["definitionURL"],
            )(*sym_operands)

        if operator.tag == f"{{{mathml_ns}}}ci":
            assert not operator.attrib
            return sp.Function(name, real=True)(*sym_operands)

        raise NotImplementedError(f"Unsupported operator {operator.tag}.")

    def handle_ci(self, element: etree._Element) -> sp.Expr:
        """Handle identifiers.

        See also:
        `numerical constants in MathML <https://www.w3.org/TR/MathML2/chapter4.html#contm.ci>`__.
        """
        handled_attrs = {
            # TODO: remove after fixing xmlns in model
            "multi:representationType",
            "multi:speciesReference",
            f"{{{self.sbml_multi_ns}}}representationType",
            f"{{{self.sbml_multi_ns}}}speciesReference",
        }
        if unhandled_attrs := (set(element.attrib.keys()) - handled_attrs):
            raise NotImplementedError(
                f"Unhandled <ci> attributes: {unhandled_attrs}"
            )

        representation_type = element.attrib.get(
            f"{{{self.sbml_multi_ns}}}representationType", None
        ) or element.attrib.get("multi:representationType", None)
        species_reference = element.attrib.get(
            f"{{{self.sbml_multi_ns}}}speciesReference", None
        ) or element.attrib.get("multi:speciesReference", None)
        symbol_name = self.preprocess_symbol_name(
            element.text.strip(), element
        )
        if representation_type or species_reference:
            return SpeciesSymbol(
                name=symbol_name,
                representation_type=representation_type,
                species_reference=species_reference,
                **self.symbol_kwargs,
            )
        return sp.Symbol(symbol_name, **self.symbol_kwargs)

    def handle_cn(self, element: etree._Element) -> sp.Expr:
        """Handle numbers.

        See also:
        `numerical constants in MathML <https://www.w3.org/TR/MathML2/chapter4.html#contm.cn>`_.
        """
        handled_attrs = {
            "type",
            f"{{{self.sbml_core_ns}}}units",
        }
        if unhandled_attrs := (set(element.attrib.keys()) - handled_attrs):
            raise NotImplementedError(
                f"Unhandled <cn> attributes: {unhandled_attrs}"
            )
        dtype = element.attrib.get("type", "real")
        converter = {
            "real": (lambda element: sp.Rational(element.text))
            if self.floats_as_rationals
            else lambda element: sp.Float(element.text),
            "integer": lambda element: sp.Integer(element.text),
            "rational": lambda element: sp.Rational(
                element.text, element[0].tail
            ),
            "e-notation":
            # this won't cycle. we don't have a corresponding
            #  representation in sympy
            lambda element: sp.Float(
                float(element.text) * 10 ** int(element[0].tail)
            ),
        }.get(dtype)
        if not converter:
            raise NotImplementedError(f"Unhandled type: {dtype}")
        obj = converter(element)

        if not self.ignore_units and (
            units := element.attrib.get(f"{{{self.sbml_core_ns}}}units", None)
        ):
            if units not in self.ureg:
                # TODO fixme: replace rhs by base units
                #  this requires access to the underlying SBML model to access
                #  unit definitions. they should be parsed during __init__.
                #  base units defined in SBML can be handled without a model,
                #  as they are not allowed to be redefined (are they?).
                #  should start from an empty UnitRegistry, as sbml could
                #  redefine any (non-base?)unit to whatever.
                self.ureg.define(f"{units} = {units}")
            # TODO pint.Quantity causes issues with sympy functions:
            #  https://docs.sympy.org/latest/explanation/active-deprecations.html#non-expr-args-deprecated
            return self.ureg.Quantity(obj, units)
        return obj

    def handle_piecewise(self, element: etree._Element) -> sp.Expr:
        expr_cond_pairs = []
        for e in element:
            # TODO: cannot currently handle functions as condition-arguments.
            #   they need to be derived from `sympy.BooleanFunction`
            #   Nested piecewise functions may work, though, if the inner
            #   expressions are all Boolean
            if e.tag == f"{{{mathml_ns}}}piece":
                assert len(e) == 2
                cond = self._parse_element(e[1])
                # Only Boolean conditions are supported
                #  -> convert
                # this won't round-trip
                cond = _num2bool(cond)
                expr_cond_pairs.append(
                    (self._parse_element(e[0]), cond),
                )
            elif e.tag == f"{{{mathml_ns}}}otherwise":
                # may occur only as last condition
                assert e is element[-1]
                assert len(e) == 1
                expr_cond_pairs.append(
                    (self._parse_element(e[0]), True),
                )
            else:
                raise AssertionError(e.tag)

        with sp.evaluate(self.evaluate):
            return sp.Piecewise(*expr_cond_pairs)

    def handle_lambda(self, element: etree._Element) -> sp.Expr:
        # See https://www.w3.org/TR/MathML2/chapter4.html#id.4.2.1.7
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
        assert element.attrib["encoding"] == "text"
        return CSymbol(
            self.preprocess_symbol_name(element.text.strip(), element),
            encoding=element.attrib["encoding"],
            definition_url=element.attrib["definitionURL"],
            **self.symbol_kwargs,
        )

    def preprocess_symbol_name(
        self, name: str, element: etree._Element = None
    ) -> str:
        """Preprocess symbol names.

        Override this method to preprocess symbol names before parsing.
        For example, to handle reserved names.

        Does nothing by default.

        :param name: Symbol name in the MathML element.
        :param element: MathML element.
        :return: Preprocessed symbol name.
        """
        return name


def _bool2num(x: sp.Basic) -> sp.Basic:
    """Convert sympy Booleans or BooleanFunctions to expressions or Integers.

    Return anything else as is
    """
    if isinstance(x, BooleanFalse):
        return sp.Integer(0)
    if isinstance(x, BooleanTrue):
        return sp.Integer(1)
    if isinstance(x, Boolean) and not isinstance(x, sp.Symbol):
        #  `Piecewise((1, expr),(0,True))`
        return Piecewise((sp.Integer(1), x), (sp.Integer(0), sp.true))

    return x


def _num2bool(x: sp.Basic) -> sp.Basic:
    """Convert non-Booleans to Boolean expressions.

    Return anything else as is.
    """
    if not isinstance(x, Boolean):
        if isinstance(x, Piecewise):
            # apply recursively to the expressiosn
            return Piecewise(
                *((_num2bool(expr), cond) for expr, cond in x.args)
            )
        return Piecewise((True, x != 0), (False, True))
    return x
