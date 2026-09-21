"""A small immutable dense-array core, with no third-party dependencies.

This module deliberately does not implement NumPy compatibility. Storage is a
C-order tuple of Python numbers, not a packed buffer. Only scalar or equal-shape
broadcasting is supported. See ``docs/scientific-scope.md`` for the contract.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from math import prod
from operator import add, mul, sub, truediv
from typing import Literal

Scalar = int | float
DType = Literal["int", "float"]
__all__ = ["Array", "array"]


def _scalar(value: object) -> Scalar:
    if type(value) not in (int, float):
        raise TypeError("array values must be Python int or float; bool is unsupported")
    return value  # type: ignore[return-value]


def _flatten(data: object) -> tuple[tuple[int, ...], tuple[Scalar, ...]]:
    if isinstance(data, Array):
        return data.shape, data.flat
    if not isinstance(data, (list, tuple)):
        return (), (_scalar(data),)
    children = [_flatten(item) for item in data]
    if not children:
        return (0,), ()
    child_shape = children[0][0]
    if any(shape != child_shape for shape, _ in children):
        raise ValueError("nested array data must be rectangular")
    return (len(children), *child_shape), tuple(x for _, values in children for x in values)


def _shape(shape: Sequence[int]) -> tuple[int, ...]:
    result = tuple(shape)
    if any(type(dim) is not int for dim in result):
        raise TypeError("shape dimensions must be Python integers")
    if any(dim < 0 for dim in result):
        raise ValueError("shape dimensions must be nonnegative; inferred dimensions are unsupported")
    return result


@dataclass(frozen=True, slots=True, init=False)
class Array:
    """Immutable, rectangular, row-major data with ``int`` or ``float`` dtype.

    ``int`` is arbitrary-precision Python int; ``float`` is Python float.
    Explicit int dtype rejects floating inputs rather than truncating them.
    Empty input defaults to int, or preserves dtype when copied from an Array.
    """

    _shape: tuple[int, ...]
    _flat: tuple[Scalar, ...]
    _dtype: DType

    def __init__(self, data: object, *, dtype: DType | None = None) -> None:
        shape, values = _flatten(data)
        if dtype is None:
            dtype = data.dtype if isinstance(data, Array) else (
                "float" if any(type(x) is float for x in values) else "int"
            )
        if dtype not in ("int", "float"):
            raise ValueError("dtype must be 'int' or 'float'")
        if dtype == "int" and any(type(x) is not int for x in values):
            raise TypeError("int dtype does not implicitly truncate floating values")
        if dtype == "float":
            values = tuple(float(x) for x in values)
        object.__setattr__(self, "_shape", shape)
        object.__setattr__(self, "_flat", values)
        object.__setattr__(self, "_dtype", dtype)

    @classmethod
    def _from_flat(cls, values: tuple[Scalar, ...], shape: tuple[int, ...], dtype: DType) -> Array:
        result = object.__new__(cls)
        object.__setattr__(result, "_shape", shape)
        object.__setattr__(result, "_flat", values)
        object.__setattr__(result, "_dtype", dtype)
        return result

    @property
    def shape(self) -> tuple[int, ...]:
        return self._shape

    @property
    def dtype(self) -> DType:
        return self._dtype

    @property
    def ndim(self) -> int:
        return len(self.shape)

    @property
    def size(self) -> int:
        return len(self.flat)

    @property
    def flat(self) -> tuple[Scalar, ...]:
        """Read-only, C-order values; sharing this immutable tuple is safe."""
        return self._flat

    def item(self) -> Scalar:
        if self.size != 1:
            raise ValueError("item() requires exactly one element")
        return self.flat[0]

    def tolist(self) -> Scalar | list:
        """Return independent nested lists, or a number for a scalar array."""
        def unpack(shape: tuple[int, ...], offset: int) -> Scalar | list:
            if not shape:
                return self.flat[offset]
            stride = prod(shape[1:])
            return [unpack(shape[1:], offset + i * stride) for i in range(shape[0])]

        return unpack(self.shape, 0)

    def __len__(self) -> int:
        if not self.shape:
            raise TypeError("a scalar array has no length")
        return self.shape[0]

    def __iter__(self) -> Iterator[Array | Scalar]:
        return (self[index] for index in range(len(self)))

    def __bool__(self) -> bool:
        raise TypeError("array truth testing is unsupported; inspect a scalar explicitly")

    def __getitem__(self, key: int | tuple[int, ...]) -> Array | Scalar:
        indices = key if isinstance(key, tuple) else (key,)
        if any(type(index) is not int for index in indices):
            raise TypeError("only integer indexing is supported; slices and masks are unsupported")
        if len(indices) > self.ndim:
            raise IndexError("too many indices for array")
        offset = 0
        for axis, index in enumerate(indices):
            dim = self.shape[axis]
            index = index + dim if index < 0 else index
            if not 0 <= index < dim:
                raise IndexError(f"index out of range on axis {axis}")
            offset += index * prod(self.shape[axis + 1:])
        remaining = self.shape[len(indices):]
        if not remaining:
            return self.flat[offset]
        count = prod(remaining)
        return self._from_flat(self.flat[offset:offset + count], remaining, self.dtype)

    def reshape(self, *shape: int | Sequence[int]) -> Array:
        """Return a new array sharing immutable storage; element count cannot change."""
        raw = shape[0] if len(shape) == 1 and isinstance(shape[0], (list, tuple)) else shape
        target = _shape(raw)  # type: ignore[arg-type]
        if prod(target) != self.size:
            raise ValueError("reshape must preserve the number of elements")
        return self._from_flat(self.flat, target, self.dtype)

    def _binary(self, other: object, operation: Callable, *, reverse: bool = False,
                division: bool = False) -> Array:
        right = other if isinstance(other, Array) else Array(other)
        if self.shape != right.shape and self.shape != () and right.shape != ():
            raise ValueError("broadcasting supports equal shapes or a scalar array only")
        shape = right.shape if self.shape == () else self.shape
        dtype: DType = "float" if division or "float" in (self.dtype, right.dtype) else "int"
        values = []
        for index in range(prod(shape)):
            left_value = self.flat[0 if self.shape == () else index]
            right_value = right.flat[0 if right.shape == () else index]
            value = operation(right_value, left_value) if reverse else operation(left_value, right_value)
            values.append(float(value) if dtype == "float" else value)
        return self._from_flat(tuple(values), shape, dtype)

    def __add__(self, other: object) -> Array:
        return self._binary(other, add)

    def __radd__(self, other: object) -> Array:
        return self + other

    def __sub__(self, other: object) -> Array:
        return self._binary(other, sub)

    def __rsub__(self, other: object) -> Array:
        return self._binary(other, sub, reverse=True)

    def __mul__(self, other: object) -> Array:
        return self._binary(other, mul)

    def __rmul__(self, other: object) -> Array:
        return self * other

    def __truediv__(self, other: object) -> Array:
        return self._binary(other, truediv, division=True)

    def __rtruediv__(self, other: object) -> Array:
        return self._binary(other, truediv, reverse=True, division=True)

    def __neg__(self) -> Array:
        return self * -1

    def _reduce(self, axis: int | None, mean: bool) -> Array | Scalar:
        zero: Scalar = 0.0 if mean or self.dtype == "float" else 0
        if axis is None:
            if mean and not self.size:
                raise ValueError("mean of an empty array is undefined")
            total = sum(self.flat, zero)
            return total / self.size if mean else total
        if type(axis) is not int:
            raise TypeError("axis must be an integer or None")
        axis = axis + self.ndim if axis < 0 else axis
        if not 0 <= axis < self.ndim:
            raise ValueError("axis out of range")
        width = self.shape[axis]
        if mean and width == 0:
            raise ValueError("mean over an empty axis is undefined")
        outer, inner = prod(self.shape[:axis]), prod(self.shape[axis + 1:])
        values = []
        for block in range(outer):
            for index in range(inner):
                total = sum((self.flat[(block * width + k) * inner + index]
                             for k in range(width)), zero)
                values.append(total / width if mean else total)
        shape = self.shape[:axis] + self.shape[axis + 1:]
        if not shape:
            return values[0]
        return self._from_flat(tuple(values), shape, "float" if mean else self.dtype)

    def sum(self, axis: int | None = None) -> Array | Scalar:
        """Sum all values or one axis; empty sums use the dtype's zero."""
        return self._reduce(axis, False)

    def mean(self, axis: int | None = None) -> Array | Scalar:
        """Arithmetic mean using Python float; reducing an empty axis raises."""
        return self._reduce(axis, True)

    def matmul(self, other: Array) -> Array:
        """Two-dimensional matrix multiplication, including zero-length axes."""
        if not isinstance(other, Array):
            raise TypeError("matmul requires another Array")
        if self.ndim != 2 or other.ndim != 2:
            raise ValueError("matmul currently supports two-dimensional arrays only")
        rows, width = self.shape
        other_width, columns = other.shape
        if width != other_width:
            raise ValueError("matmul inner dimensions must match")
        dtype: DType = "float" if "float" in (self.dtype, other.dtype) else "int"
        zero: Scalar = 0.0 if dtype == "float" else 0
        values = tuple(sum((self.flat[row * width + k] * other.flat[k * columns + column]
                            for k in range(width)), zero)
                       for row in range(rows) for column in range(columns))
        return self._from_flat(values, (rows, columns), dtype)

    def __matmul__(self, other: Array) -> Array:
        return self.matmul(other)


def array(data: object, *, dtype: DType | None = None) -> Array:
    """Construct an immutable Array from a number, nested lists/tuples, or Array."""
    return Array(data, dtype=dtype)
