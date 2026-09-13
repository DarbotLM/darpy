# DARPy

**Distributed Architecture Reasoning and Planning — the DarbotLabs Python platform.**

DARPy is growing from a multi-robot coverage planner into reusable computation,
task execution, agent teams, and measured improvement. The platform exposes
`darpy`; its companion [Darbot Python SDK](https://github.com/DarbotLM/darpy-sdk)
exposes `darpy_sdk` for protocol and client/server integration.

This is a working foundation release with deliberately scoped capabilities.
Full NumPy and SymPy parity, a complete SWE agent, distributed swarms, and
recursive optimizer training are specified workstreams. They are not claimed
as implemented by this release.

| Capability | Current scope |
| --- | --- |
| Core contracts | Validated, versioned JSON task, budget, and execution records |
| Runtime | Injected asynchronous handlers with deadlines, cancellation, and concurrency limits |
| Agent teams | Named local runtimes, ordered results, explicit failure handling |
| Scientific primitives | Native immutable arrays and exact rational polynomial expressions |
| Improvement | Evidence-based candidate promotion against a fixed evaluation contract |
| Robot coverage | Repaired legacy DARP/STC planner, optional numerical dependencies, headless operation |
| Protocols | MCP, Agent Client Protocol, and Microsoft Activity integration belong to the companion SDK |

## Develop locally

Python 3.12 or newer is required. From this repository:

```bash
uv sync --frozen
uv run --frozen darpy doctor
uv run --frozen pytest
```

Enable the legacy robot planner with `uv sync --frozen --extra coverage`.
Visualization is separately optional: `uv sync --frozen --extra visualization`.
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

## Documentation

- [Full platform specification](docs/platform-specification.md)
- [Implemented scope and release gates](docs/implementation-status.md)
- [Runtime, teams, and improvement](docs/core-runtime.md)
- [Native scientific scope](docs/scientific-scope.md)
- [Legacy coverage integration](docs/legacy-coverage.md)
- [Original coverage research and attribution](docs/original-coverage-readme.md)
- [Source provenance and publication requirements](NOTICE.md)

The specification covers the complete destination, including scientific parity,
architecture reasoning, SWE agents, distributed recovery, SkillOpt-informed
improvement, package ownership, and migration across DarbotLabs. Capability
status and tests determine what can be relied on in the current code.
