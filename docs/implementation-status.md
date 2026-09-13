# Implementation status

The 0.1.0 development foundation implements the surfaces below. The full
[platform specification](platform-specification.md) remains the product target.
No benchmark or full-library compatibility certification is inferred from a
passing subset of tests.

| Surface | Implementation | Remaining boundary |
| --- | --- | --- |
| Contracts | Strict JSON dataclass records and validation | Full cross-service schema family and migrations |
| Execution | Local asynchronous handler runtime and bounded task execution | Process, container, and remote worker isolation |
| Teams | Named local runtimes and explicit per-task outcomes | Distributed leases, coordinator recovery, and durable state |
| Arrays | Immutable dense primitives with an explicit numerical scope | NumPy dtype/storage/API/ABI semantics and complete public inventory |
| Symbolic math | Exact rational polynomial operations | SymPy assumptions, domains, solvers, functions, and complete public inventory |
| Charts | Native line, scatter, bar, histogram, labels, legend, and deterministic SVG | Full Matplotlib Artist/API behavior, layout, text, projections, backends, and rendering parity |
| Improvement | Fixed-contract evaluation evidence and strict candidate promotion | Skill generation, rollout training, sealed evaluation harness, canary deployment |
| Coverage | Legacy planner repairs, native input validation, headless integration | Full spatial planner modernization and workload performance baselines |
| SDK protocols | Separate companion repository with explicit protocol contracts | SDK refactor and integration test gates described in the specification |

## Evaluation discipline

The local tests verify implemented behavior: task serialization, budget and
cancellation semantics, team outcomes, mathematical invariants, evaluation
eligibility, and coverage connectivity. They do not establish generalized agent
intelligence, automatic recursive improvement, global path optimality, or parity
with a mature scientific library.

Microsoft SkillOpt supplies the design inspiration for treating skill documents
as editable external state, proposing bounded changes, and retaining only
evaluated improvements. The current promotion module implements an evidence
gate. It does not run SkillOpt or retrain models.

## Release conditions

The repository is prepared for development use with a reproducible lockfile and
Windows/Linux CI. Public package publication still requires the inherited-source
license decision recorded in [NOTICE](../NOTICE.md), platform matrix evidence,
artifact verification, and a release decision. CI configuration is not evidence
that every hosted matrix job has already passed.

The first complete platform release additionally requires the SWE vertical
slice and other acceptance scenarios in the specification. This foundation
release does not silently mark those gates complete.
