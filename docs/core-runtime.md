# DARPy core runtime

DARPy provides an owned, dependency-free execution foundation. Applications
supply asynchronous handlers; the core validates requests, enforces cooperative
execution budgets, and returns receipts. It does not choose a model, perform
tool calls, or implement an autonomous software engineer by itself.

The core is written with the Python standard library. `native` in the capability
registry means DARPy owns that implementation; it does not mean compiled machine
code. `scoped` marks a working implementation with explicit limits. `planned`
marks a target that this release does not implement. Installing a package or
registering a capability does not establish scientific or protocol conformance.

## Execute a task

```python
import asyncio
from darpy import RunBudget, Runtime, Task

async def handler(task: Task) -> str:
    return task.prompt.upper()

async def main() -> None:
    runtime = Runtime(
        handler,
        budget=RunBudget(timeout_seconds=10, max_input_chars=10_000, max_output_chars=2_000),
        max_concurrency=2,
    )
    result = await runtime.run(Task("Plan a release", session_id="release-1"))
    print(result.text)
    print(result.to_json())

asyncio.run(main())
```

`Task` has a prompt, nonempty session and request IDs, protocol provenance,
optional working-directory context, and an optional JSON payload string.
Request IDs default to a random UUID hex string. Protocol values are `local`,
`mcp`, `acp`, and `activity`. Setting this field records where the request came
from; the core does not start any protocol server or client. SDK adapters can
translate wire requests into these contracts and use `Runtime.run`.

The working-directory field is descriptive. DARPy never changes the process
working directory on behalf of concurrent requests. A handler that accesses
files must apply its own approved workspace policy.

`RunResult` contains successful output text, task and session IDs, protocol, and
elapsed wall-clock seconds. It is an execution receipt, not evidence that the
answer is correct. Handler exceptions propagate unchanged. Budget failures raise
`BudgetExceededError` with `limit` equal to `input`, `output`, or `time`.

## Budget and cancellation behavior

- The runtime semaphore bounds handlers active on one `Runtime` instance.
  Waiting for this semaphore consumes the task deadline.
- Input size counts Unicode characters in all task string fields, including IDs,
  protocol, working-directory context, and the serialized payload. Output size
  counts Unicode characters in returned text. These are not token or byte limits.
- Input overflow prevents handler execution. Output overflow is detected after
  the handler returns; it cannot prevent output allocation or undo side effects.
- Timeout cancels cooperative work and releases the concurrency slot after
  cleanup. A handler's own `TimeoutError` remains a handler failure; it is not
  incorrectly classified as the runtime deadline.
- Caller cancellation propagates. Runtime deadline expiry cannot become a
  successful receipt if a handler catches the cancellation and returns late.
- A runtime binds to its first running event loop. Reusing it from another loop
  raises an error, including sequential calls through separate `asyncio.run`s.
- There are no automatic retries or request deduplication. The application owns
  idempotency, side-effect transaction boundaries, and any retry policy.

Handlers must yield and honor cancellation. Python task cancellation cannot
preempt blocking native code or a coroutine that never yields. Cleanup can also
take longer than the deadline. Returned late results are rejected, but this
mechanism is not a hard execution-time limit, process sandbox, memory limiter,
token accountant, or spend controller. Use an isolated worker process when those
properties are necessary. Concurrent pending callers consume application memory;
the runtime bounds active execution, not total admission from external clients.

## Validated contracts and schemas

```python
from darpy.schemas import RunBudget, Task, schema

request = Task("Describe the change", "review", payload_json='{"branch":"feature"}')
restored = Task.from_json(request.to_json())
assert restored == request
print(schema("Task"))
```

`Task`, `RunBudget`, and `RunResult` are frozen dataclasses with runtime validation
and versioned JSON serialization. `from_dict` and `from_json` require
`schema_version` equal to `1.0`, reject unknown fields, and run constructor
validation. Serialized payloads reject malformed JSON, duplicate object keys,
and nonfinite floating-point values. Numeric limits reject booleans, nonfinite
values, and invalid ranges. Integer character limits require Python integers.

`schema(name)` returns a fresh JSON Schema 2020-12 object for each public
execution contract. Its `urn:darpy:schema:1.0:...` identifier is an identifier,
not a claimed hosted endpoint. JSON Schema's `contentMediaType` is an annotation;
Python constructor validation also parses `payload_json` strictly. Task creation
and JSON parsing happen before `Runtime.run`; the runtime deadline does not bound
that parsing work. API ingress should cap raw request sizes before decoding.

## Coordinate local agents

```python
import asyncio
from darpy import Runtime, Task
from darpy.teams import Team, WorkItem

async def summarize(task: Task) -> str:
    return "Summary: " + task.prompt

async def inspect(task: Task) -> str:
    return "Review: " + task.prompt

async def main() -> None:
    team = Team(
        {"writer": Runtime(summarize), "reviewer": Runtime(inspect)},
        max_concurrency=2,
        max_tasks=100,
    )
    result = await team.run([
        WorkItem("writer", Task("release notes", "release")),
        WorkItem("reviewer", Task("release risks", "release")),
    ], failure_mode="collect")
    for outcome in result.outcomes:
        print(outcome.agent, outcome.status, outcome.result)

asyncio.run(main())
```

A `Team` maps explicit agent names to runtimes. Every accepted work item receives
an outcome in input order. Status is `succeeded`, `failed`, `budget_exceeded`, or
`cancelled`. Successful outcomes include a matching `RunResult`; other outcomes
carry an exception type and message. Team receipts serialize and round-trip
through `TeamResult.to_json` and `TeamResult.from_json`. Handler error messages
are application-provided text; the core does not redact them automatically.

The default `collect` mode permits independent tasks to finish after sibling
failure. `fail_fast` cancels unfinished work when a failure is observed, waits for
cleanup, retains completed successes, and records cancellation outcomes. Because
scheduling is concurrent, some work may complete before a failure is observed.
There is no transaction rollback. Cancelling the calling coroutine cancels its
children and propagates cancellation after cleanup instead of returning a result.

Unknown agents, duplicate request IDs, invalid items, and an exceeded task cap
are rejected before execution begins. A generator is consumed only as far as the
configured cap plus one item, so an unbounded input iterable cannot be fully
materialized. An empty batch yields a successful result with no outcomes.

The team concurrency limit applies to a single `Team.run` batch across all named
agents. Each runtime's own limit applies across its calls. Waiting for the team
semaphore precedes `Runtime.run` and is not included in that runtime deadline;
applications can wrap the entire team run in `asyncio.timeout` for a batch-level
deadline. Simultaneous batches have independent team semaphores. All of this
executes in one process: durable queues, distributed leases, fencing, consensus,
recovery after process loss, and swarm scheduling remain planned capabilities.

## Compare improvement evidence

```python
from dataclasses import replace
from darpy.improve import CheckResult, EvaluationEvidence, EvaluationSpec, ImprovementGate

spec = EvaluationSpec(
    evaluator_id="release-checks@sha256:fixed-evaluator-content",
    dataset_id="heldout@sha256:fixed-dataset-content",
    metric="task_success_rate",
    required_checks=("correctness", "regressions"),
)
baseline = EvaluationEvidence(
    artifact_id="skill:release-planner",
    artifact_version="v1",
    evaluator_id=spec.evaluator_id,
    dataset_id=spec.dataset_id,
    metric=spec.metric,
    score=0.75,
    sample_count=100,
    checks=(CheckResult("correctness", True), CheckResult("regressions", True)),
)
# Example measurements only; these values are not DARPy benchmark results.
candidate = replace(baseline, artifact_version="v2", score=0.80)
record = ImprovementGate(spec).evaluate(baseline, candidate)
print(record.reason, record.selected_version)
print(record.to_json())
```

The gate follows SkillOpt's principle of retaining a baseline unless a candidate
shows strict improvement on fixed validation evidence. DARPy's current module is
only the evidence comparison and receipt layer. Microsoft SkillOpt also generates
rollouts, reflects on errors, proposes bounded skill-document edits, and performs
consolidation; DARPy does not claim those optimizer stages are implemented here.
See the [official SkillOpt repository](https://github.com/microsoft/SkillOpt).

The comparison requires matching evaluator, dataset, metric, sample count, and
artifact identity, with distinct artifact versions. All required correctness
checks must exist and pass for both baseline and candidate. A missing check is
a failure. Metrics and derived improvement must be finite. The direction can be
`maximize` or `minimize`; improvement must be strictly greater than
`min_improvement`, including when that threshold is zero. Ties retain the baseline.
Different metrics, datasets, or evaluator identities are incomparable evidence.

Each `PromotionRecord` contains schema version `1.0`, a unique record ID, UTC
timestamp, frozen comparison specification, both evidence objects, improvement
when comparable and finite, the decision, and its reason. The gate never mutates
an artifact or automatically deploys a selected version. Persist these records
in the application's artifact store if decisions must survive the process.

Evidence IDs are caller assertions; the gate checks equality rather than fetching
or attesting evaluator code and dataset contents. Use immutable, content-addressed
identities and stable evaluation settings in a real pipeline. The example identity
strings above are illustrative, not calculated hashes. The gate does not prove
statistical significance or enforce an optimizer's search budget. Fixed holdouts,
validation-use limits, paired samples, independent final evaluation, and protected
deployment controls are pipeline responsibilities. Repeated selection against the
same holdout can overfit it even when every individual comparison is valid.

## Inspect without starting a model

```console
darpy doctor
darpy capabilities
darpy schema Task
python -m darpy schema RunResult
```

These commands write JSON to standard output, require no credentials or network,
and do not start an agent or import optional protocol packages. `doctor` reports
local version and platform facts and explicitly reports that full NumPy and
SymPy parity are not achieved. The capability registry currently exposes native
runtime and schema ownership, scoped local teams, scoped evidence gates, scoped
scientific primitives, and planned full parity and distributed swarm work.
