"""Behavioral tests for the bounded legacy-planner compatibility repairs."""
# Scientific dependencies are optional; skip before importing legacy modules.
# ruff: noqa: E402

import os
import subprocess
import sys
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("numba")
pytest.importorskip("cv2")

from CalculateTrajectories import CalculateTrajectories
from darp import DARP, CalcConnectedMultiplier
from Edges import Edge
from kruskal import Kruskal
from multiRobotPathPlanner import MultiRobotPathPlanner, get_area_map


def planner(**changes):
    arguments = dict(
        nx=3,
        ny=4,
        notEqualPortions=False,
        given_initial_positions=[0, 11],
        given_portions=[],
        obstacles_positions=[],
        visualization=False,
        MaxIter=100,
    )
    arguments.update(changes)
    return DARP(**arguments)


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"nx": 0}, "nx"),
        ({"ny": -1}, "ny"),
        ({"nx": 2.5}, "nx"),
        ({"nx": True}, "nx"),
        ({"given_initial_positions": []}, "at least one"),
        ({"given_initial_positions": [0, 0]}, "duplicates"),
        ({"given_initial_positions": [-1]}, "inside the grid"),
        ({"given_initial_positions": [12]}, "inside the grid"),
        ({"given_initial_positions": [1.5]}, "integer indices"),
        ({"given_initial_positions": [True]}, "integer indices"),
        ({"obstacles_positions": [12]}, "inside the grid"),
        ({"obstacles_positions": [1, 1]}, "duplicates"),
        ({"obstacles_positions": [0]}, "overlap"),
        ({"obstacles_positions": [4, 5, 6, 7]}, "connected"),
        ({"notEqualPortions": True, "given_portions": [-1, 2]}, "finite fractions"),
        ({"notEqualPortions": True, "given_portions": [0, 1]}, "finite fractions"),
        ({"notEqualPortions": True, "given_portions": [float("nan"), 1]}, "finite fractions"),
        ({"notEqualPortions": True, "given_portions": [float("inf"), 1]}, "finite fractions"),
        ({"notEqualPortions": True, "given_portions": [0.3, 0.3]}, "sum to 1"),
        ({"notEqualPortions": True, "given_portions": [1]}, "one fraction"),
        ({"MaxIter": 0}, "MaxIter"),
        ({"dcells": -1}, "dcells"),
        ({"randomLevel": float("nan")}, "randomLevel"),
        ({"CCvariation": 1}, "CCvariation"),
        ({"seed": -1}, "seed"),
    ],
)
def test_invalid_inputs_raise_value_error(changes, message):
    with pytest.raises(ValueError, match=message):
        planner(**changes)


def assert_connected(cells, start):
    pending = [start]
    visited = {start}
    while pending:
        row, col = pending.pop()
        for neighbor in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
            if neighbor in cells and neighbor not in visited:
                visited.add(neighbor)
                pending.append(neighbor)
    assert visited == cells


@pytest.mark.parametrize(
    "rows, cols, starts, obstacles",
    [
        (2, 2, [0], []),
        (3, 4, [0, 11], [5]),
        (1, 1, [0], []),
        (1, 2, [0, 1], []),
    ],
)
def test_successful_coverage_is_connected_complete_and_closed(rows, cols, starts, obstacles, capsys):
    result = MultiRobotPathPlanner(rows, cols, False, starts, [], obstacles, False, MaxIter=100)
    assert result.DARP_success
    darp = result.darp_instance
    assert not capsys.readouterr().out
    assert result.execution_time >= 0
    np.testing.assert_array_equal(darp.BinaryRobotRegions.sum(axis=0), darp.GridEnv != -2)
    for robot, start in enumerate(darp.initial_positions):
        cells = set(map(tuple, np.argwhere(darp.BinaryRobotRegions[robot])))
        assert start in cells
        assert_connected(cells, start)
        path = result.best_case.paths[robot]
        assert len(path) == 4 * len(cells)
        assert path[0][:2] == (2 * start[0], 2 * start[1])
        assert path[-1][2:] == path[0][:2]
        assert len({edge[:2] for edge in path}) == len(path)
        for index, (row, col, next_row, next_col) in enumerate(path):
            assert abs(row - next_row) + abs(col - next_col) == 1
            assert (row // 2, col // 2) in cells
            assert (next_row // 2, next_col // 2) in cells
            assert (next_row, next_col) == path[(index + 1) % len(path)][:2]


def test_numpy_integer_inputs_and_last_iteration_success():
    instance = planner(nx=np.int64(4), ny=np.int32(4), given_initial_positions=np.array([0, 1]), MaxIter=1, dcells=0)
    success, iterations = instance.divideRegions()
    assert success and iterations == 1
    assert instance.MaxIter == 1
    np.testing.assert_array_equal(instance.ArrayOfElements, [7, 7])


def test_unequal_portions_converge_deterministically_without_global_rng_changes():
    original = np.random.get_state()
    try:
        np.random.seed(831)
        before = np.random.get_state()
        left = planner(nx=4, ny=5, given_initial_positions=[0, 19], notEqualPortions=True, given_portions=[0.2, 0.8])
        right = planner(nx=4, ny=5, given_initial_positions=[0, 19], notEqualPortions=True, given_portions=[0.2, 0.8])
        assert left.divideRegions() == right.divideRegions()
        np.testing.assert_array_equal(left.A, right.A)
        assert np.all(np.abs(left.ArrayOfElements - left.DesireableAssign) <= left.termThr)
        after = np.random.get_state()
        assert before[0] == after[0] and before[2:] == after[2:]
        np.testing.assert_array_equal(before[1], after[1])
    finally:
        np.random.set_state(original)


def test_iteration_exhaustion_is_observable_and_preserves_budget():
    instance = planner(nx=5, ny=5, given_initial_positions=[0, 1], MaxIter=1, dcells=1)
    success, iterations = instance.divideRegions()
    assert not success
    assert iterations == 1 and instance.MaxIter == 1


@pytest.mark.parametrize("mode", range(4))
def test_four_neighbor_mst_has_minimum_cost_and_no_cycles(mode):
    tree = Kruskal(2, 2)
    tree.initializeGraph(np.ones((2, 2), dtype=bool), True, mode)
    tree.performKruskal()
    assert len(tree.mst) == 3
    assert sum(edge.weight for edge in tree.mst) == 3
    components = [{node} for node in range(4)]
    for edge in tree.mst:
        source = next(group for group in components if edge.src in group)
        target = next(group for group in components if edge.dst in group)
        assert source is not target
        source.update(target)
        components.remove(target)
    assert components == [{0, 1, 2, 3}]


@pytest.mark.parametrize("region", [np.eye(3, dtype=bool), np.fliplr(np.eye(3, dtype=bool))])
def test_eight_neighbor_mst_connects_both_diagonal_directions(region):
    tree = Kruskal(3, 3)
    tree.initializeGraph(region, True, 0)
    tree.performKruskal()
    assert tree.mst == []
    tree.initializeGraph(region, False, 0)
    tree.performKruskal()
    assert len(tree.mst) == 2
    assert {node for edge in tree.mst for node in (edge.src, edge.dst)} == set(np.flatnonzero(region))
    assert sum(edge.weight for edge in tree.mst) == 2


def test_constant_normalizations_are_finite():
    instance = planner(nx=1, ny=1, given_initial_positions=[0], importance=True)
    np.testing.assert_array_equal(instance.NormalizedEuclideanDistanceBinary(True, np.ones((1, 1))), [[1]])
    np.testing.assert_array_equal(instance.NormalizedEuclideanDistanceBinary(False, np.ones((1, 1))), [[0]])
    np.testing.assert_array_equal(instance.calculateCriterionMatrix(np.ones((1, 1)), 1, 1, 1.2, True), [[1.2]])
    np.testing.assert_array_equal(CalcConnectedMultiplier(1, 1, np.zeros((1, 1)), np.zeros((1, 1)), 0.01), [[1]])


def test_import_does_not_change_process_state_or_require_graphics():
    code = """
import os, random, sys
import numpy as np
before_env = dict(os.environ)
before_print = np.get_printoptions()
before_random = random.getstate()
before_numpy = np.random.get_state()
import darp, multiRobotPathPlanner, Visualization
assert 'pygame' not in sys.modules
assert 'sklearn' not in sys.modules
assert 'PIL' not in sys.modules
assert dict(os.environ) == before_env
assert np.get_printoptions() == before_print
assert random.getstate() == before_random
after_numpy = np.random.get_state()
assert before_numpy[0] == after_numpy[0] and before_numpy[2:] == after_numpy[2:]
np.testing.assert_array_equal(before_numpy[1], after_numpy[1])
"""
    completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert completed.stdout == ""


def test_coverage_facade_does_not_eagerly_load_scientific_dependencies():
    root = Path(__file__).resolve().parents[1]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(root / "src")
    code = "import sys; import darpy.coverage; assert not {'numpy', 'numba', 'cv2', 'pygame'} & sys.modules.keys()"
    subprocess.run([sys.executable, "-c", code], env=environment, capture_output=True, text=True, check=True)


def test_image_maps_support_grayscale_and_ignore_alpha(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    grayscale = tmp_path / "gray.png"
    Image.fromarray(np.array([[0, 255]], dtype=np.uint8)).save(grayscale)
    np.testing.assert_array_equal(get_area_map(grayscale), [[-1, 0]])
    rgba = tmp_path / "rgba.png"
    Image.fromarray(np.array([[[0, 0, 0, 255], [255, 255, 255, 0]]], dtype=np.uint8)).save(rgba)
    np.testing.assert_array_equal(get_area_map(rgba), [[-1, 0]])


def test_trajectory_diagonal_graph_and_missing_edge_error():
    trajectory = CalculateTrajectories(1, 1, [])
    trajectory.initializeGraph(np.fliplr(np.eye(2, dtype=bool)), False)
    assert Edge(1, 2, 1) in trajectory.allEdges
    assert Edge(2, 1, 1) in trajectory.allEdges
    with pytest.raises(RuntimeError, match="missing an edge"):
        trajectory.SafeRemoveEdge(Edge(0, 3, 1))
