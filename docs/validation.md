# Foundation validation

Validated locally on 13 September 2026 using Python 3.12.14 on Linux and the committed uv lockfile.

- `uv run --frozen pytest`: 114 tests and 44 subtests passed.
- `uv run --frozen ruff check src/darpy tests`: passed.
- `uv run --frozen pyright`: zero errors.
- `git diff --check`: passed.
- `uv build`: source distribution and wheel built successfully.
- An isolated installed wheel exercised native array multiplication and exact polynomial differentiation with NumPy absent.
- An isolated installed wheel with the coverage dependencies planned a headless 2 by 2 single-robot grid successfully.
- Independent scientific review compared 228 array cases and 1,458 exact polynomial evaluations with reference calculations; all passed.

The wheel includes the inherited coverage modules and typed DARPy package. Its base installation has no mandatory third-party dependencies. The optional coverage check used NumPy 2.5.3, Numba 0.67.0, and OpenCV headless 5.0.0.93.

These checks verify the scoped foundation. They do not certify NumPy/SymPy parity, performance superiority, distributed operation, or a trained autonomous agent. Hosted Windows and Python 3.13 jobs are configured in CI and remain separate evidence. Publication conditions are recorded in [NOTICE](../NOTICE.md).
