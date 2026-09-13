from dataclasses import FrozenInstanceError
from fractions import Fraction

import pytest

from darpy.symbolic import Expr, Number, Symbol, symbols, sympify


def test_exact_rationals_canonical_equality_and_hash():
    x = Symbol("x")
    assert Number(Fraction(1, 3)) + Fraction(2, 3) == 1
    assert x / 3 + 2 * x / 3 == x
    assert x - x == 0
    assert Number(0).value == Fraction(0)
    assert Number(Fraction(2, 6)).value == Fraction(1, 3)
    assert hash(Number(2)) == hash(2)
    assert hash(Number(Fraction(1, 3))) == hash(Fraction(1, 3))
    assert len({x + x, 2 * x}) == 1
    assert sympify(x) is x
    assert Expr() == 0


def test_polynomial_ring_identities():
    x, y, z = symbols("x", "y", "z")
    assert (x + y) ** 3 == x**3 + 3*x**2*y + 3*x*y**2 + y**3
    assert (x + y) * z == x*z + y*z
    assert (x + y) + z == x + (y + z)
    assert (x * y) * z == x * (y * z)
    assert (x - y) * (x + y) == x**2 - y**2
    assert (x + y) * (x - y) == (x - y) * (x + y)
    assert x**0 == 1 and Expr(0)**0 == 1
    assert (x - x).free_symbols == frozenset()
    assert (x + y + y*x).free_symbols == frozenset({"x", "y"})


def test_exact_formal_derivatives_and_product_rule():
    x, y = symbols("x", "y")
    f, g = x**3 / 3 + 2*x*y, x**2 - y
    assert f.diff(x) == x**2 + 2*y
    assert f.diff("y") == 2*x
    assert (f*g).diff(x) == f.diff(x)*g + f*g.diff(x)
    assert (x**5).diff(x, 3) == 60*x**2
    assert (x**5).diff(x, 6) == 0
    assert f.diff(x, 0) is f
    assert f.diff("z") == 0
    assert f.diff(x).diff(y) == f.diff(y).diff(x)


def test_simultaneous_substitution_and_exact_evaluation():
    x, y = symbols("x", "y")
    f = x**2 + x*y + Fraction(1, 7)
    assert f.subs({x: Fraction(1, 3), "y": Fraction(2, 5)}) == Fraction(122, 315)
    assert (x + 2*y).subs({x: y, y: x}) == y + 2*x
    assert (x**2).subs({x: y + 1}) == y**2 + 2*y + 1
    assert f.substitute({"z": 12}) == f
    assert f.subs({}) == f
    with pytest.raises(ValueError, match="duplicate"):
        f.subs({x: 1, "x": 2})


def test_immutable_expression_storage():
    x = Symbol("x")
    expression = x + 1
    assert expression.terms == (((), Fraction(1)), ((("x", 1),), Fraction(1)))
    with pytest.raises(FrozenInstanceError):
        expression._terms = ()
    with pytest.raises(FrozenInstanceError):
        x._terms = ()
    assert x.name == "x"


@pytest.mark.parametrize("value", [True, 0.1, "x + 1", 1j, None])
def test_inexact_and_parsed_values_are_not_silently_coerced(value):
    with pytest.raises(TypeError):
        sympify(value)
    with pytest.raises(TypeError):
        Number(value)
    with pytest.raises(TypeError):
        Expr(0) * value


def test_domain_boundaries_fail_explicitly():
    x = Symbol("x")
    with pytest.raises(NotImplementedError, match="rational constant"):
        x / (x + 1)
    with pytest.raises(ZeroDivisionError):
        x / 0
    with pytest.raises(ValueError, match="negative"):
        x**-1
    with pytest.raises(TypeError, match="integers"):
        x**Fraction(1, 2)
    with pytest.raises(TypeError, match="integers"):
        x**True
    with pytest.raises(ValueError, match="nonnegative"):
        x.diff(x, -1)
    with pytest.raises(TypeError, match="integer"):
        x.diff(x, 1.0)
    with pytest.raises(TypeError, match="truth"):
        bool(x)
    for name in ["", "x y", "x + 1", 1]:
        with pytest.raises(ValueError, match="identifier"):
            Symbol(name)


def test_human_readable_display_and_symbol_factory():
    x, = symbols("x")
    assert str(x**2 + Fraction(1, 3)*x - 2) == "x**2 + 1/3*x - 2"
    assert str(Number(0)) == "0"
    assert str(-x) == "-x"
    assert symbols() == ()
