"""Cooperative asynchronous execution with bounded local concurrency."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Literal

from .schemas import RunBudget, RunResult, Task, _positive_int

Handler = Callable[[Task], Awaitable[str]]


class BudgetExceededError(RuntimeError):
    """A declared budget failed. ``limit`` identifies input, output, or time."""

    def __init__(self, message: str, *, limit: Literal["input", "output", "time"]) -> None:
        super().__init__(message)
        self.limit = limit


class Runtime:
    """Execute a supplied async handler in one event loop.

    Limits require cooperative handlers that yield and honor cancellation.
    This is not a sandbox: use process isolation for blocking/untrusted code.
    The runtime owns no model, transport, credential, filesystem, or network.
    """

    def __init__(self, handler: Handler, *, budget: RunBudget | None = None, max_concurrency: int = 4) -> None:
        if not callable(handler):
            raise TypeError("handler must be callable")
        _positive_int(max_concurrency, "max_concurrency")
        if budget is not None and not isinstance(budget, RunBudget):
            raise TypeError("budget must be a RunBudget")
        self.handler = handler
        self.budget = budget if budget is not None else RunBudget()
        self.max_concurrency = max_concurrency
        self._slots = asyncio.Semaphore(max_concurrency)
        self._loop: asyncio.AbstractEventLoop | None = None

    async def run(self, task: Task) -> RunResult:
        """Return a successful receipt or propagate failure/cancellation.

        A handler's own ``TimeoutError`` is preserved. Runtime deadline expiry
        becomes ``BudgetExceededError(limit='time')``. Callers retain ownership
        of retries and side-effect idempotency; requests are never auto-retried.
        """
        if not isinstance(task, Task):
            raise TypeError("task must be a Task")
        loop = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = loop
        elif self._loop is not loop:
            raise RuntimeError("Runtime cannot be shared across event loops")
        input_size = sum(
            len(value)
            for value in (
                task.prompt,
                task.session_id,
                task.protocol,
                task.request_id,
                task.cwd or "",
                task.payload_json or "",
            )
        )
        if input_size > self.budget.max_input_chars:
            raise BudgetExceededError("Input character budget exceeded", limit="input")
        started = time.monotonic()
        current = asyncio.current_task()
        cancellation_count = current.cancelling() if current is not None else 0
        deadline = asyncio.timeout(self.budget.timeout_seconds)
        try:
            async with deadline:
                async with self._slots:
                    output = await self.handler(task)
        except TimeoutError as exc:
            if deadline.expired():
                raise BudgetExceededError("Execution time budget exceeded", limit="time") from exc
            raise
        # A cooperative handler may catch cancellation; a late result must not
        # be reported as success even when it suppresses the deadline signal.
        if deadline.expired() or time.monotonic() - started > self.budget.timeout_seconds:
            raise BudgetExceededError("Execution time budget exceeded", limit="time")
        if current is not None and current.cancelling() > cancellation_count:
            raise asyncio.CancelledError
        if not isinstance(output, str):
            raise TypeError("Runtime handlers must return text")
        if len(output) > self.budget.max_output_chars:
            raise BudgetExceededError("Output character budget exceeded", limit="output")
        return RunResult(task.request_id, task.session_id, task.protocol, output, time.monotonic() - started)


__all__ = ["BudgetExceededError", "Handler", "RunBudget", "RunResult", "Runtime", "Task"]
