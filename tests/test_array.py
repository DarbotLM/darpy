from dataclasses import FrozenInstanceError

import pytest

from darpy.array import Array, array


def test_rectangular_storage_and_indexing():
    a = array([[[1, 2], [3, 4]], [[5, 6], [7, 8]]])
    assert a.shape == (2, 2, 2)
    assert a.ndim == 3 and a.size == 8 and a.dtype == "int"
    assert a.flat == (1, 2, 3, 4, 5, 6, 7, 8)
    assert a[-1, 0, -1] == 6
    assert a[1].tolist() == [[5, 6], [7, 8]]
    assert a[0, 1].tolist() == [3, 4]
    assert array(7)[()] == 7


def test_copy_and_reshape_cannot_alias_mutable_inputs_or_outputs():
    source = [[1, 2], [3, 4]]
    a = array(source)
    source[0][0] = 99
    exported = a.tolist()
    exported[0][0] = 88
    reshaped = a.reshape(4)
    assert a.tolist() == [[1, 2], [3, 4]]
    assert reshaped.flat is a.flat
    assert array(a).flat is a.flat
    with pytest.raises(FrozenInstanceError):
        a._flat = (10,)
    with pytest.raises(TypeError):
        a[0] = 10


def test_numeric_dtype_contract():
    assert array([1, 2.5]).flat == (1.0, 2.5)
    assert array([1, 2.5]).dtype == "float"
    assert array([10**100]).item() == 10**100
    assert array([], dtype="float").dtype == "float"
    assert array(array([], dtype="float")).dtype == "float"
    assert array([1], dtype="float").flat == (1.0,)
    with pytest.raises(TypeError, match="truncate"):
        array([2.0], dtype="int")
    with pytest.raises(ValueError, match="dtype"):
        array([1], dtype="int64")


@pytest.mark.parametrize("data", [[True], ["1"], [1j], object()])
def test_unsupported_values_are_rejected(data):
    with pytest.raises(TypeError, match="Python int or float"):
        array(data)


def test_shape_and_index_errors_are_explicit():
    with pytest.raises(ValueError, match="rectangular"):
        array([[1], [2, 3]])
    a = array([[1, 2], [3, 4]])
    for index in [2, -3, (0, 0, 0)]:
        with pytest.raises(IndexError):
            a[index]
    for index in [slice(None), True, (0, slice(None)), [0]]:
        with pytest.raises(TypeError, match="integer indexing"):
            a[index]
    with pytest.raises(ValueError, match="preserve"):
        a.reshape(3)
    with pytest.raises(ValueError, match="nonnegative"):
        a.reshape(-1)
    with pytest.raises(TypeError, match="integers"):
        a.reshape(2.0, 2)
    with pytest.raises(TypeError, match="truth"):
        bool(a)


def test_scalar_and_zero_length_shapes():
    a = array(3)
    assert a.shape == () and a.size == 1 and a.tolist() == 3
    assert a.reshape((1, 1)).tolist() == [[3]]
    assert array([3]).reshape(()).item() == 3
    with pytest.raises(TypeError):
        len(a)
    with pytest.raises(TypeError):
        iter(a)
    empty = array([[], []])
    assert empty.shape == (2, 0) and empty.size == 0
    assert empty[1].tolist() == []
    assert empty.reshape(0, 3).tolist() == []
    assert empty.sum() == 0
    assert empty.sum(1).tolist() == [0, 0]
    with pytest.raises(ValueError, match="empty"):
        empty.mean()
    with pytest.raises(ValueError, match="empty"):
        empty.mean(1)
    with pytest.raises(ValueError):
        empty.item()


def test_elementwise_algebra_and_limited_broadcasting():
    a = array([[1, 2], [3, 4]])
    b = array([[4, 3], [2, 1]])
    assert ((a + b) - b) == a
    assert (a * (b + 2)) == a * b + a * 2
    assert (10 - a).tolist() == [[9, 8], [7, 6]]
    assert (array(2) * a).tolist() == [[2, 4], [6, 8]]
    assert (-a).tolist() == [[-1, -2], [-3, -4]]
    assert (a / 2).tolist() == [[0.5, 1.0], [1.5, 2.0]]
    assert (12 / a).tolist() == [[12.0, 6.0], [4.0, 3.0]]
    assert (a / 2).dtype == "float"
    assert (array([]) + array(1.0)).dtype == "float"
    with pytest.raises(ValueError, match="broadcasting"):
        a + array([1, 2])
    with pytest.raises(ValueError, match="broadcasting"):
        array([1, 2]) + array([1])
    with pytest.raises(ZeroDivisionError):
        a / 0


def test_reductions_across_each_axis_and_dtype():
    a = array([[[1, 2], [3, 4]], [[5, 6], [7, 8]]])
    assert a.sum() == 36
    assert a.mean() == 4.5
    assert a.sum(0).tolist() == [[6, 8], [10, 12]]
    assert a.sum(1).tolist() == [[4, 6], [12, 14]]
    assert a.sum(-1).tolist() == [[3, 7], [11, 15]]
    assert a.mean(0).tolist() == [[3.0, 4.0], [5.0, 6.0]]
    assert a.mean(0).dtype == "float"
    assert array([1, 2]).sum(0) == 3
    assert array([], dtype="float").sum() == 0.0
    assert type(array([], dtype="float").sum()) is float
    assert array([]).reshape(0, 3).sum(0).tolist() == [0, 0, 0]
    assert array([]).reshape(0, 3).mean(1).shape == (0,)
    with pytest.raises(ValueError, match="axis"):
        a.sum(3)
    with pytest.raises(ValueError, match="axis"):
        array(1).sum(0)
    with pytest.raises(TypeError, match="axis"):
        a.sum(True)


def test_matrix_product_identity_distributivity_and_rectangular_result():
    a = array([[1, 2, 3], [4, 5, 6]])
    b = array([[7, 8], [9, 10], [11, 12]])
    identity = array([[1, 0], [0, 1]])
    assert (a @ b).tolist() == [[58, 64], [139, 154]]
    assert identity @ a == a
    assert (a @ b) @ identity == a @ b
    assert a @ (b + b) == (a @ b) + (a @ b)
    assert (identity @ array([[1.0], [2.0]])).dtype == "float"


def test_matrix_product_degenerate_shapes_and_errors():
    result = array([[], []]) @ array([]).reshape(0, 3)
    assert result.shape == (2, 3)
    assert result.tolist() == [[0, 0, 0], [0, 0, 0]]
    assert (array([]).reshape(0, 2) @ array([[1], [2]])).shape == (0, 1)
    with pytest.raises(ValueError, match="two-dimensional"):
        array([1]) @ array([1])
    with pytest.raises(ValueError, match="inner dimensions"):
        array([[1, 2]]) @ array([[1, 2]])
    with pytest.raises(TypeError, match="another Array"):
        array([[1]]) @ [[1]]


def test_iteration_yields_scalars_or_subarrays():
    assert list(array([1, 2])) == [1, 2]
    assert list(array([[1, 2]])) == [Array([1, 2])]
