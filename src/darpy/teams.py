"""Bounded local agent teams with explicit per-task outcomes."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal, Self

from .runtime import BudgetExceededError, Runtime
from .schemas import SCHEMA_VERSION, JsonContract, RunResult, Task, _positive_int, _string


@dataclass(frozen=True, slots=True)
class WorkItem:
    agent: str
    task: Task

    def __post_init__(self) -> None:
        _string(self.agent, "agent")
        if not isinstance(self.task, Task):
            raise TypeError("task must be a Task")


@dataclass(frozen=True, slots=True)
class TaskOutcome:
    agent: str
    request_id: str
    status: Literal["succeeded", "failed", "budget_exceeded", "cancelled"]
    result: RunResult | None = None
    error_type: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        _string(self.agent, "agent")
        _string(self.request_id, "request_id")
        if self.status not in ("succeeded", "failed", "budget_exceeded", "cancelled"):
            raise ValueError("Unknown task outcome status")
        if self.status == "succeeded":
            if not isinstance(self.result, RunResult) or self.result.request_id != self.request_id:
                raise ValueError("Successful outcomes require a matching RunResult")
            if self.error_type is not None or self.error_message is not None:
                raise ValueError("Successful outcomes cannot contain errors")
        else:
            if self.result is not None:
                raise ValueError("Unsuccessful outcomes cannot contain a success receipt")
            _string(self.error_type, "error_type")
            _string(self.error_message, "error_message", nonempty=False)


@dataclass(frozen=True, slots=True)
class TeamResult(JsonContract):
    """Ordered outcomes. A result exists for every accepted work item."""

    outcomes: tuple[TaskOutcome, ...]

    def __post_init__(self) -> None:
        if type(self.outcomes) is not tuple or not all(isinstance(item, TaskOutcome) for item in self.outcomes):
            raise TypeError("outcomes must be a tuple of TaskOutcome objects")
        if len({item.request_id for item in self.outcomes}) != len(self.outcomes):
            raise ValueError("Outcome request IDs must be unique")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Self:
        if not isinstance(value, dict) or set(value) != {"schema_version", "outcomes"}:
            raise ValueError("TeamResult requires only schema_version and outcomes")
        if value["schema_version"] != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")
        if not isinstance(value["outcomes"], (list, tuple)):
            raise TypeError("outcomes must be an array")
        outcomes: list[TaskOutcome] = []
        for item in value["outcomes"]:
            if not isinstance(item, dict):
                raise TypeError("Each outcome must be an object")
            data = dict(item)
            if data.get("result") is not None:
                data["result"] = RunResult.from_dict({"schema_version": SCHEMA_VERSION, **data["result"]})
            outcomes.append(TaskOutcome(**data))
        return cls(tuple(outcomes))

    @property
    def succeeded(self) -> bool:
        return all(outcome.status == "succeeded" for outcome in self.outcomes)


class Team:
    """Coordinate named runtimes in this process; no distributed scheduling.

    ``collect`` allows independent tasks to finish after a sibling failure.
    ``fail_fast`` cancels remaining work, retains completed successes, and emits
    cancellation outcomes. Both modes preserve input order. Caller cancellation
    propagates after child cleanup; it never becomes a successful TeamResult.
    """

    def __init__(
        self,
        agents: Mapping[str, Runtime],
        *,
        max_concurrency: int = 4,
        max_tasks: int = 1_000,
    ) -> None:
        _positive_int(max_concurrency, "max_concurrency")
        _positive_int(max_tasks, "max_tasks")
        if not isinstance(agents, Mapping) or not agents:
            raise ValueError("agents must be a nonempty mapping")
        for name, runtime in agents.items():
            _string(name, "agent name")
            if not isinstance(runtime, Runtime):
                raise TypeError("Each agent must be a Runtime")
        self._agents = dict(agents)
        self.max_concurrency = max_concurrency
        self.max_tasks = max_tasks

    async def run(
        self,
        items: Iterable[WorkItem],
        *,
        failure_mode: Literal["collect", "fail_fast"] = "collect",
    ) -> TeamResult:
        if failure_mode not in ("collect", "fail_fast"):
            raise ValueError("failure_mode must be 'collect' or 'fail_fast'")
        work: list[WorkItem] = []
        identifiers: set[str] = set()
        for item in items:
            if len(work) >= self.max_tasks:
                raise ValueError("Team task limit exceeded")
            if not isinstance(item, WorkItem):
                raise TypeError("Each item must be a WorkItem")
            if item.agent not in self._agents:
                raise ValueError(f"Unknown agent: {item.agent}")
            if item.task.request_id in identifiers:
                raise ValueError("Task request IDs must be unique within a team run")
            identifiers.add(item.task.request_id)
            work.append(item)
        slots = asyncio.Semaphore(self.max_concurrency)

        async def execute(item: WorkItem) -> TaskOutcome:
            try:
                async with slots:
                    receipt = await self._agents[item.agent].run(item.task)
                return TaskOutcome(item.agent, item.task.request_id, "succeeded", result=receipt)
            except Exception as exc:
                status = "budget_exceeded" if isinstance(exc, BudgetExceededError) else "failed"
                return TaskOutcome(
                    item.agent, item.task.request_id, status, error_type=type(exc).__name__, error_message=str(exc)
                )

        tasks = [asyncio.create_task(execute(item)) for item in work]
        try:
            pending = set(tasks)
            while pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                failed = any(task.cancelled() or task.result().status != "succeeded" for task in done)
                if failure_mode == "fail_fast" and failed:
                    for task in pending:
                        task.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)
                    break
        except BaseException:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        outcomes = tuple(
            TaskOutcome(
                item.agent,
                item.task.request_id,
                "cancelled",
                error_type="CancelledError",
                error_message="Task execution was cancelled",
            )
            if task.cancelled()
            else task.result()
            for item, task in zip(work, tasks, strict=True)
        )
        return TeamResult(outcomes)


__all__ = ["TaskOutcome", "Team", "TeamResult", "WorkItem"]
