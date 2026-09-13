"""Exact, canonical multivariate polynomials over rational coefficients.

This is a deliberately bounded symbolic core, not SymPy compatibility. It has
no parser, floating-point coercion, transcendental functions or equation solver.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

Monomial = tuple[tuple[str, int], ...]
Terms = tuple[tuple[Monomial, Fraction], ...]
__all__ = ["Expr", "Number", "Symbol", "symbols", "sympify"]


def _name(value: str | Symbol) -> str:
    name = value.name if isinstance(value, Symbol) else value
    if not isinstance(name, str) or not name.isidentifier():
        raise ValueError("a symbol name must be a nonempty Python identifier")
    return name


@dataclass(frozen=True, slots=True, init=False, eq=False)
class Expr:
    """Immutable expanded polynomial, automatically combining equal monomials."""

    _terms: Terms

    def __init__(self, value: int | Fraction | Expr = 0) -> None:
        if isinstance(value, Expr):
            terms = value.terms
        elif type(value) is int or isinstance(value, Fraction):
            number = Fraction(value)
            terms = (((), number),) if number else ()
        else:
            raise TypeError("exact expressions accept int or Fraction, not floats, strings or bool")
        object.__setattr__(self, "_terms", terms)

    @classmethod
    def _from_terms(cls, terms: Mapping[Monomial, Fraction]) -> Expr:
        result = object.__new__(Expr)
        object.__setattr__(result, "_terms", tuple(sorted((m, c) for m, c in terms.items() if c)))
        return result

    @property
    def terms(self) -> Terms:
        """Canonical immutable pairs of monomial and exact rational coefficient."""
        return self._terms

    @property
    def free_symbols(self) -> frozenset[str]:
        """Names of variables with nonzero powers in the canonical polynomial."""
        return frozenset(name for monomial, _ in self.terms for name, _ in monomial)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Expr):
            return self.terms == other.terms
        if type(other) is int or isinstance(other, Fraction):
            return self.terms == Expr(other).terms
        return NotImplemented

    def __hash__(self) -> int:
        if not self.terms:
            return hash(Fraction(0))
        if len(self.terms) == 1 and self.terms[0][0] == ():
            return hash(self.terms[0][1])
        return hash(self.terms)

    def __bool__(self) -> bool:
        raise TypeError("expression truth testing is unsupported; compare with zero explicitly")

    def __add__(self, other: int | Fraction | Expr) -> Expr:
        terms = dict(self.terms)
        for monomial, coefficient in sympify(other).terms:
            terms[monomial] = terms.get(monomial, Fraction(0)) + coefficient
        return self._from_terms(terms)

    def __radd__(self, other: int | Fraction | Expr) -> Expr:
        return self + other

    def __neg__(self) -> Expr:
        return self._from_terms({m: -c for m, c in self.terms})

    def __sub__(self, other: int | Fraction | Expr) -> Expr:
        return self + -sympify(other)

    def __rsub__(self, other: int | Fraction | Expr) -> Expr:
        return sympify(other) - self

    def __mul__(self, other: int | Fraction | Expr) -> Expr:
        right = sympify(other)
        terms: dict[Monomial, Fraction] = {}
        for left_m, left_c in self.terms:
            for right_m, right_c in right.terms:
                powers = dict(left_m)
                for name, power in right_m:
                    powers[name] = powers.get(name, 0) + power
                monomial = tuple(sorted(powers.items()))
                terms[monomial] = terms.get(monomial, Fraction(0)) + left_c * right_c
        return self._from_terms(terms)

    def __rmul__(self, other: int | Fraction | Expr) -> Expr:
        return self * other

    def __truediv__(self, other: int | Fraction | Expr) -> Expr:
        denominator = sympify(other)
        if denominator.free_symbols:
            raise NotImplementedError("division is supported only by a rational constant")
        if not denominator.terms:
            raise ZeroDivisionError("division by zero")
        return self * (1 / denominator.terms[0][1])

    def __pow__(self, exponent: int) -> Expr:
        if type(exponent) is not int:
            raise TypeError("polynomial exponents must be Python integers")
        if exponent < 0:
            raise ValueError("negative powers are outside the polynomial domain")
        result, base = Expr(1), self
        while exponent:
            if exponent & 1:
                result = result * base
            exponent //= 2
            if exponent:
                base = base * base
        return result

    def subs(self, replacements: Mapping[str | Symbol, int | Fraction | Expr]) -> Expr:
        """Simultaneously substitute variables; replacements are not re-substituted."""
        normalized = {}
        for key, value in replacements.items():
            name = _name(key)
            if name in normalized:
                raise ValueError(f"duplicate substitution for {name!r}")
            normalized[name] = sympify(value)
        result = Expr(0)
        for monomial, coefficient in self.terms:
            term = Expr(coefficient)
            for name, power in monomial:
                term = term * normalized.get(name, Symbol(name)) ** power
            result = result + term
        return result

    def substitute(self, replacements: Mapping[str | Symbol, int | Fraction | Expr]) -> Expr:
        return self.subs(replacements)

    def diff(self, variable: str | Symbol, order: int = 1) -> Expr:
        """Exact formal partial derivative; order zero returns this expression."""
        name = _name(variable)
        if type(order) is not int:
            raise TypeError("derivative order must be a Python integer")
        if order < 0:
            raise ValueError("derivative order must be nonnegative")
        result = self
        for _ in range(order):
            terms = {}
            for monomial, coefficient in result.terms:
                powers = dict(monomial)
                power = powers.get(name, 0)
                if power:
                    if power == 1:
                        del powers[name]
                    else:
                        powers[name] = power - 1
                    terms[tuple(sorted(powers.items()))] = coefficient * power
            result = self._from_terms(terms)
            if not result.terms:
                break
        return result

    def __str__(self) -> str:
        if not self.terms:
            return "0"
        parts = []
        ordered = sorted(self.terms, key=lambda item: (-sum(p for _, p in item[0]), item[0]))
        for monomial, coefficient in ordered:
            factors = [name if power == 1 else f"{name}**{power}" for name, power in monomial]
            magnitude = abs(coefficient)
            if magnitude != 1 or not factors:
                factors.insert(0, str(magnitude))
            body = "*".join(factors)
            parts.append(("-" if coefficient < 0 else "") + body if not parts else
                         (" - " if coefficient < 0 else " + ") + body)
        return "".join(parts)

    def __repr__(self) -> str:
        return f"Expr({str(self)})"


class Number(Expr):
    """An exact rational constant, constructed from int or Fraction."""

    __slots__ = ()

    def __init__(self, value: int | Fraction = 0) -> None:
        if not (type(value) is int or isinstance(value, Fraction)):
            raise TypeError("Number requires an int or Fraction")
        super().__init__(value)

    @property
    def value(self) -> Fraction:
        return self.terms[0][1] if self.terms else Fraction(0)


class Symbol(Expr):
    """A named indeterminate with no implicit assumptions or bound value."""

    __slots__ = ()

    def __init__(self, name: str) -> None:
        object.__setattr__(self, "_terms", ((((_name(name), 1),), Fraction(1)),))

    @property
    def name(self) -> str:
        return self.terms[0][0][0][0]


def sympify(value: int | Fraction | Expr) -> Expr:
    """Coerce exact values only. Strings are not evaluated or parsed."""
    return value if isinstance(value, Expr) else Expr(value)


def symbols(*names: str) -> tuple[Symbol, ...]:
    """Create symbols with ``symbols('x', 'y')``; always returns a tuple."""
    return tuple(Symbol(name) for name in names)
