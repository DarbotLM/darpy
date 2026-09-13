# Native scientific core scope

DARPy's first scientific slice is a dependency-free reference implementation of
immutable dense arrays and exact rational polynomials. It establishes concrete,
tested behavior that later backends can preserve. It does **not** provide NumPy
or SymPy feature parity, packed native kernels, or a demonstrated performance
advantage. Full compatibility remains a separate, substantially larger program
in the platform specification.

## Dense arrays

```python
from darpy.array import array

a = array([[1, 2], [3, 4]])
assert (a @ a).tolist() == [[7, 10], [15, 22]]
assert (a + 2).sum() == 18
assert a.mean(axis=0).tolist() == [2.0, 3.0]
assert a.reshape(4).flat == (1, 2, 3, 4)
```

`Array(data, dtype=None)` and `array(data, dtype=None)` accept Python int/float,
rectangular nested lists or tuples, or another Array. Bool, complex, object,
strings, generators, and foreign numerical scalars are rejected. The immutable
public metadata is `shape`, `ndim`, `size`, and `dtype`; `flat` exposes the
immutable C-order tuple. A scalar has shape `()` and size one. Empty arrays
preserve dimensions: `[[], []]` has shape `(2, 0)`.

| Surface | Implemented contract |
| --- | --- |
| Dtypes | `"int"` is arbitrary-precision Python int; `"float"` is Python float, normally IEEE binary64. These are not fixed-width NumPy dtypes. Mixed values promote to float. Explicit int rejects float inputs, including integral floats. Empty input defaults to int; copying an Array preserves dtype. |
| Storage | Python tuple in C order, containing Python numbers. Nested mutable input is copied into immutable storage. Array copies and reshape may share immutable tuples. `tolist()` creates independent mutable nested lists. No writable views or buffer protocol. |
| Indexing | Integer and tuples of integers, including negative indices. Full indexing returns a Python number. Partial indexing returns an immutable subarray. Iteration follows the first axis. Scalar arrays have no length or iteration. `item()` accepts exactly one element. |
| Reshape | `reshape(2, 3)` or `reshape((2, 3))`; nonnegative dimensions and identical element count required. `reshape(())` produces a scalar only for one element. No inferred `-1`, strides, transpose, or alternate order. |
| Arithmetic | Elementwise `+`, `-`, `*`, `/`, unary minus and reflected scalar operations. Only equal shapes or scalar shape `()` broadcast. Division always produces float and uses Python division errors. Empty elementwise operations perform no scalar arithmetic. |
| Reductions | `sum(axis=None)` and `mean(axis=None)` over all values or one integer axis, including negative axes. Full reduction or a scalar result returns a Python number; otherwise an Array. Empty sums are zero. Reducing an empty axis with mean raises ValueError; an empty output over a nonempty axis is valid. No axis tuples, keepdims, dtype, out, or mask parameters. |
| Matrix product | `a @ b` or `a.matmul(b)` for two 2D Arrays. Inner dimensions must match. Zero inner dimensions produce a zero matrix; zero outer dimensions are preserved. No vector promotion or batch broadcasting. |
| Equality | Structural Python bool equality includes shape, dtype, and values. This is not elementwise comparison. Array truth testing always raises TypeError. |

Python integer arithmetic does not overflow at a fixed bit width. Conversion to
float may raise OverflowError for values beyond Python float range. Floating
operations use Python semantics, including NaN and infinity; no custom IEEE error
mode or deterministic cross-platform reduction guarantee is provided. Reduction
order follows C-order traversal. This Python implementation prioritizes explicit
behavior and correctness, and allocates output storage for arithmetic. It does
not claim to outperform native numerical libraries.

Missing capabilities include general broadcasting, slices and advanced indexing,
mutation, fixed-width dtype promotion, ufuncs, random numbers, FFTs, linear solvers,
sparse arrays, GPU execution, autograd, subclass dispatch, and the NumPy C API/ABI.
Calling unsupported arguments or operations produces a Python error; there is
no automatic fallback that would disguise an external dependency as native code.

## Exact symbolic polynomials

```python
from fractions import Fraction
from darpy.symbolic import symbols

x, y = symbols("x", "y")
f = (x + y)**3 / 3
assert f.diff(x) == (x + y)**2
assert (x / 3 + 2*x / 3) == x
assert (x + 2*y).subs({x: y, y: x}) == y + 2*x
assert f.subs({x: Fraction(1, 2), y: Fraction(1, 2)}) == Fraction(1, 3)
```

`Expr`, `Number`, `Symbol`, `symbols`, and `sympify` live in `darpy.symbolic`.
Expressions are immutable canonical sparse multivariate polynomials over exact
`fractions.Fraction` coefficients. Addition and multiplication expand and combine
equal monomials. `terms` exposes immutable `(monomial, coefficient)` pairs;
monomials are sorted tuples of `(name, positive_integer_power)`. Zero has no terms.
`free_symbols` is a frozenset of variable **names**, not Symbol objects.

| Surface | Implemented contract |
| --- | --- |
| Constants | `Expr(2)`, `Number(Fraction(1, 3))`, or `sympify(value)` accept Python int, Fraction, and, for Expr/sympify, existing expressions. Number exposes an exact `value`. Float, bool, complex and strings are rejected. Use an explicit Fraction when an exact decimal value is required. |
| Symbols | `Symbol("x")` uses a nonempty Python identifier. Symbols are formal indeterminates without assumptions. `symbols("x", "y")` always returns a tuple; it does not parse a space-delimited expression. |
| Operations | Exact addition, subtraction, multiplication, unary minus, and nonnegative integer powers. Division is supported only by a nonzero rational constant. Power zero returns one, including `0**0`, by the formal polynomial convention. |
| Equality | Canonical polynomial equality; expression equality with an int or Fraction is also supported, with compatible hashes. No approximate comparison, equation object, or automatic Boolean truth evaluation. |
| Substitution | `subs(mapping)` and `substitute(mapping)` accept symbol names or Symbol keys and exact expression values. Substitution is simultaneous. Unused names have no effect; duplicate keys naming the same variable are rejected. |
| Derivatives | `diff(variable, order=1)` computes a formal partial derivative in a name or Symbol. Nonnegative integer order only; order zero returns the original expression. |

There is no parser or string evaluation. Rational functions with symbolic
denominators, negative/fractional powers, assumptions, unevaluated expression
trees, transcendental functions, integration, equation solving, matrices,
arbitrary-precision approximate evaluation, code generation, or general SymPy API
compatibility are not implemented. Polynomial expansion can consume substantial
memory for large powers or many variables; the module is not an untrusted-input
resource sandbox. Runtime job limits should bound work using these operations.

## Verification and extension gates

The tests check array shape and dtype behavior, rejection of ambiguous operations,
input/output alias safety, empty dimensions, axis reductions, matrix identities,
and exact symbolic ring identities, the product rule, mixed partial derivatives,
rational substitution and simultaneous substitution. They use only pytest in the
development environment; neither module imports NumPy or SymPy at runtime.

Future additions must publish the new behavior and its limitations, add independent
mathematical or reference conformance checks, and update the compatibility inventory.
Packed buffers, native kernels and external adapters must remain distinguishable
from this reference core. Performance claims require recorded workloads and
measurements; adding an adapter is not evidence of native feature parity.
