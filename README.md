# DARPy

**Distributed Architecture Reasoning and Planning — the DarbotLabs Python platform.**

DARPy is growing from a multi-robot coverage planner into reusable computation,
task execution, agent teams, and measured improvement. The platform exposes
`darpy`; its companion [Darbot Python SDK](https://github.com/DarbotLM/darpy-sdk)
exposes `darpy_sdk` for protocol and client/server integration.

This is a working foundation release with deliberately scoped capabilities.
Full NumPy, SymPy, and Matplotlib parity, a complete SWE agent, distributed swarms, and
recursive optimizer training are specified workstreams. They are not claimed
as implemented by this release.

| Capability | Current scope |
| --- | --- |
| Core contracts | Validated, versioned JSON task, budget, and execution records |
| Runtime | Injected asynchronous handlers with deadlines, cancellation, and concurrency limits |
| Agent teams | Named local runtimes, ordered results, explicit failure handling |
| Scientific primitives | Native immutable arrays and exact rational polynomial expressions |
| Charts | Native line, scatter, bar, histogram, labels, legends, and deterministic SVG export |
| Improvement | Evidence-based candidate promotion against a fixed evaluation contract |
| Robot coverage | Repaired legacy DARP/STC planner, optional numerical dependencies, headless operation |
| Protocols | MCP, Agent Client Protocol, and Microsoft Activity integration belong to the companion SDK |

## Develop locally

Python 3.14 is the supported development and CI baseline. Package metadata
requires Python 3.14 or newer. From this repository:

```bash
uv python install 3.14
uv sync --frozen
uv run --frozen darpy doctor
uv run --frozen pytest
```

Enable the legacy robot planner with `uv sync --frozen --extra coverage`.
Visualization is separately optional: `uv sync --frozen --extra visualization`.
It includes Matplotlib 3.11.2 or newer and pygame-ce, which provides the
`pygame` module with Python 3.14 wheels. Keep the selected extra on subsequent
`uv run` commands, or use `uv run --frozen --all-extras pytest` for the full suite.
The base package has no third-party runtime requirements and does not load
numerical libraries, model providers, or network services on import.

## Run a task

```python
import asyncio

from darpy import Runtime, Task


async def handler(task: Task) -> str:
    return f"Completed: {task.prompt}"


async def main() -> None:
    runtime = Runtime(handler, max_concurrency=4)
    result = await runtime.run(Task("inspect this project", session_id="example"))
    print(result.text)


asyncio.run(main())
```

A successful execution receipt means the handler completed. Application-specific
verifiers must establish that its output satisfies the user's goal. Deadlines
are cooperative: blocking or untrusted workloads need process isolation.

## Generate a native chart

Generate a chart with the dependency-free native API:

```python
from darpy.plot import subplots

figure, axes = subplots()
axes.plot([1, 2, 3], [2, 5, 4], label="Completed tasks")
axes.set_xlabel("Iteration")
axes.set_ylabel("Tasks")
axes.legend()
figure.savefig("progress.svg")
```

This release supports one numeric, linear Axes per figure. Its immutable series
and SVG output have an explicit native contract; Matplotlib's full Artist API,
interactive backends, raster export, and complete behavior remain tracked work.

## Documentation

- [Full platform specification](docs/platform-specification.md)
- [Implemented scope and release gates](docs/implementation-status.md)
- [Runtime, teams, and improvement](docs/core-runtime.md)
- [Native scientific scope](docs/scientific-scope.md)
- [Native plotting scope and Matplotlib parity roadmap](docs/plotting-scope.md)
- [Legacy coverage integration](docs/legacy-coverage.md)
- [Original coverage research and attribution](docs/original-coverage-readme.md)
- [Source provenance and publication requirements](NOTICE.md)

The specification covers the complete destination, including scientific parity,
architecture reasoning, SWE agents, distributed recovery, SkillOpt-informed
improvement, package ownership, and migration across DarbotLabs. Capability
status and tests determine what can be relied on in the current code.
