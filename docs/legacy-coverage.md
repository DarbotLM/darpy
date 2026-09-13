# Legacy coverage planner

DARPy preserves the existing grid area allocation and spanning-tree coverage
planner as an optional capability. This is a bounded compatibility repair of the
inherited implementation, not a new distributed robotics controller or a full
planner rewrite.

## Installation and use

```bash
uv sync --frozen --extra coverage
uv run --frozen --extra coverage python -c "from darpy.coverage import DARP; print(DARP)"
```

Python 3.14 is the supported runtime baseline. Development wheels can be built
with `uv build --python 3.14` and added to a consuming project
with uv. Public package publication is a separate release step. The
`visualization` extra additionally installs pygame-ce 2.5.8 or newer (the
`pygame` import) and Matplotlib 3.11.2 or newer. pygame-ce supplies Python 3.14
wheels, which the previous pygame distribution lacks. `Dependencies.sh` remains a
Bash compatibility helper and now creates an environment using uv with the
dependencies declared in `pyproject.toml`.

```python
from darpy.coverage import MultiRobotPathPlanner

plan = MultiRobotPathPlanner(
    3, 4,                 # rows, columns
    False,                # equal portions
    [0, 11],              # flattened initial cell indices
    [],                   # ignored when equal portions are requested
    [5],                  # flattened obstacle indices
    False,                # headless
    MaxIter=100,
    seed=1,
)
if plan.DARP_success:
    paths = plan.best_case.paths
else:
    # Retry with another configuration or report that this bounded search failed.
    paths = None
```

The legacy class names `DARP`, `MultiRobotPathPlanner`, and `Kruskal` are
preserved. Existing imports from the root modules remain valid. The
`darpy.coverage` facade is lazy: importing the facade alone loads no scientific
or graphics dependency. Requesting planner classes loads NumPy and Numba;
constructing a planner loads OpenCV. Graphics and image loading are requested
separately. Headless planning does not import pygame, scikit-learn, or Pillow.

## Input and result contract

- Grid dimensions are positive integers. NumPy integer scalars are accepted;
  booleans and fractional dimensions are rejected.
- Initial positions contain at least one unique integer index in
  `[0, rows * cols)`. Obstacles use the same index range, must be unique, and
  cannot overlap initial positions.
- All traversable cells must form one component under four-neighbor adjacency.
  Disconnected maps raise `ValueError` even when each component has a robot.
- Unequal portions require one finite fraction in `(0, 1]` per robot, with an
  absolute sum error strictly smaller than `0.0001`. Equal portions are generated
  internally. As in the inherited algorithm, fractions apply to traversable
  cells excluding robot start cells; each robot also owns its start cell.
- `MaxIter` is a positive integer, `dcells` is a nonnegative integer,
  `CCvariation` and `randomLevel` lie in `[0, 1)`, and `seed` is `None` or an
  integer in `[0, 2**32)`. The default seed is `1`.
- `DARP.divideRegions()` returns `(success, iterations)`. The iteration count
  describes the final tolerance attempt, preserving the legacy return shape;
  it is not the sum across all tolerance attempts. `MaxIter` is preserved on the
  instance while the internal per-attempt budget is reduced as before.
- `MultiRobotPathPlanner.DARP_success` reports bounded-search success. A failed
  search leaves `best_case` as `None`; `execution_time` is available on both
  success and failure. Invalid inputs raise exceptions rather than terminating
  the host process.
- Paths contain `(row, column, next_row, next_column)` moves on a grid with twice
  the original resolution. The tested successful plans visit all four subcells
  of every allocated cell and return to each robot's initial subcell.

## Repairs included

The NumPy 2 removed `np.float_` annotation is replaced with standard Python
`float`. Importing the legacy planner no longer resets Python/NumPy random
generators, rewrites `PYTHONHASHSEED`, changes NumPy display settings, or prints
initial conditions. Each DARP instance owns a NumPy `RandomState`; deterministic
color generation uses separate generators and does not consume the optimizer's
sequence. Third-party native libraries may still perform their own process
initialization when a planner is constructed.

Constant distance/importance normalization and grids consisting only of robot
start cells are handled without division by zero. A solution found on the final
allowed iteration is retained. Metric corrections default to a neutral
multiplier, and binary region output is cleared before regeneration.

Both diagonal directions in `Kruskal.initializeGraph(..., connect4=False, ...)`
are fixed. Reinitializing a Kruskal instance clears the previous graph. The
trajectory graph's corresponding diagonal branch is repaired, and missing
required edges raise `RuntimeError` rather than `SystemExit`. Normal coverage
planning continues to use four-neighbor spanning trees and trajectories.

Visualization uses a direct aspect-preserving scale instead of importing
scikit-learn for `MinMaxScaler`. Closing the allocation window raises
`InterruptedError`; closing a final path window returns from its event loop.
`get_area_map` loads Pillow only when called, supports grayscale/RGB/RGBA images,
and determines black obstacles from RGB channels, ignoring alpha.

## Validation and limits

Run the focused suite using:

```bash
uv run --frozen --extra coverage python -m pytest tests/test_legacy_coverage.py -q
```

The suite checks invalid input boundaries, deterministic unequal allocation,
global RNG isolation, import behavior, final-iteration success, search exhaustion,
singleton and obstacle grids, complete/closed paths, four-neighbor MST minimum
cost and acyclicity, and diagonal connectivity. No historical pickle fixtures
are loaded: executable pickle serialization is unnecessary for these invariants.

The repaired code was exercised with CPython 3.14.7, NumPy 2.5.3, Numba 0.67.0,
OpenCV headless 5.0.0.93, and Pillow 12.3.0. These observations are not a claim
that every upstream version or operating system is supported.

The inherited optimizer remains centralized, heuristic, and synchronous. It
does not guarantee convergence, globally minimal turns, collision avoidance
between timed robots, or byte-identical output across dependency versions and
platforms. Numba first-use compilation contributes startup latency. Large-map
performance, interactive graphics, and exhaustive robot/obstacle configurations
still need dedicated validation. Direct eight-neighbor graph construction is
tested; generating coverage trajectories from diagonal spanning trees is not a
supported public behavior. The broader DARPy platform roadmap does not change
these concrete limits.
