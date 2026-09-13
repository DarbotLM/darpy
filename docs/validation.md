# Python 3.14 validation

Validated locally on 13 September 2026 using CPython 3.14.7 on Linux x64 and the
committed uv lockfile. Python 3.14 is the development and CI baseline; package
metadata rejects older interpreters. The base package retains zero mandatory
third-party dependencies.

## Local checks

- `uv sync --frozen --python 3.14 --all-extras`: installed successfully into a
  clean Python 3.14 environment.
- `uv run --frozen --all-extras pytest -q`: 156 tests and 44 subtests passed,
  including 42 plotting cases and the Matplotlib 3.11.2 reference comparison.
- The rebuilt wheel's suite in an isolated base environment passed 112 tests
  and 44 subtests. Two optional checks skipped: the coverage module suite
  requires NumPy, and the Matplotlib comparison requires its reference package.
- `uv run --frozen --all-extras ruff check src/darpy tests`: passed.
- `uv run --frozen --all-extras pyright`: zero errors and warnings.
- `uv lock --check` and `git diff --check`: passed.
- `uv build --python 3.14`: source distribution and wheel built successfully.
- An isolated installed base wheel exercised native array multiplication, exact
  polynomial differentiation, and SVG plotting. NumPy, Numba, OpenCV, pygame,
  and Matplotlib were unavailable in that environment; wheel metadata contained
  no unconditional third-party requirements.
- The final native plotting source rendered line, scatter, bar, and histogram
  SVGs with site-packages disabled. Its complete import list uses only Python
  standard-library modules.
- Both tracked notebooks have Python 3.14 kernel metadata, current planner API
  examples, and cleared inherited outputs/execution counts. All nine code cells
  compiled and executed successfully under Python 3.14.7 in separate headless
  processes, each with a 60-second timeout. Both examples found a valid initial
  allocation (`iterations == 0`), produced paths of 20 and 24 edges, and reported
  combined turn counts of 5 and 9. pygame remained unloaded. This verified cell
  execution outside Jupyter; notebook frontend/kernel integration was not run,
  and saved execution counts and outputs remain empty.
- An isolated installed wheel with the coverage extra produced a complete,
  closed 16-edge coverage path for a 2 by 2 single-robot grid. Graphics modules
  remained unloaded.
- A pygame-ce smoke check rendered an allocation with SDL's dummy video/audio
  drivers and exercised allocation/path window quit handling. Matplotlib's Agg
  backend produced a valid PNG from a line plot.

## Optional dependency baseline

`uv lock --upgrade` selected these stable releases, and their imports succeeded
on Python 3.14.7. Optional dependency floors match this verified baseline.

| Distribution | Version | Extra |
| --- | --- | --- |
| NumPy | 2.5.3 | coverage, visualization |
| Numba | 0.67.0 | coverage, visualization |
| OpenCV headless | 5.0.0.93 | coverage, visualization |
| Pillow | 12.3.0 | coverage, visualization |
| pygame-ce | 2.5.8 | visualization |
| Matplotlib | 3.11.2 | visualization |

pygame-ce supplies the same `pygame` import with Python 3.14 wheels. The former
pygame 2.6.1 distribution has no compatible 3.14 wheels. A binary-only Windows
x64 resolution of the visualization extra succeeded for all 16 runtime
distributions, including DARPy. This checks artifact availability; it does not
execute Windows binaries.

CI is configured to install all extras, import scientific/graphics dependencies,
run tests, lint and type checks, and build distributions on Python 3.14 under
Linux and Windows. Hosted job results remain separate evidence from these local
checks. Interactive desktop graphics and other operating systems have not been
validated locally.

These checks verify the scoped foundation. They do not certify full
NumPy/SymPy/Matplotlib parity, performance superiority, distributed operation,
or a trained autonomous agent. Publication conditions are recorded in
[NOTICE](../NOTICE.md).
