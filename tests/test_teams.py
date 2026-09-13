import asyncio
import unittest

from darpy import RunBudget, Runtime, Task
from darpy.teams import Team, TeamResult, WorkItem


class TeamTests(unittest.IsolatedAsyncioTestCase):
    async def test_collect_preserves_order_and_independent_success(self):
        async def handler(task):
            if task.prompt == "bad":
                raise ValueError("cannot complete")
            return task.prompt.upper()

        work = [
            WorkItem("writer", Task(prompt, "s", request_id=str(i))) for i, prompt in enumerate(["one", "bad", "three"])
        ]
        result = await Team({"writer": Runtime(handler)}).run(work)
        self.assertEqual([item.status for item in result.outcomes], ["succeeded", "failed", "succeeded"])
        self.assertEqual([item.request_id for item in result.outcomes], ["0", "1", "2"])
        self.assertEqual(result.outcomes[2].result.text, "THREE")
        self.assertEqual(result.outcomes[1].error_type, "ValueError")
        self.assertFalse(result.succeeded)
        self.assertEqual(TeamResult.from_json(result.to_json()), result)

    async def test_fail_fast_cancels_running_sibling_and_cleans_up(self):
        started, cleaned = asyncio.Event(), asyncio.Event()

        async def handler(task):
            if task.prompt == "bad":
                await started.wait()
                raise ValueError("failure")
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.set()

        team = Team({"agent": Runtime(handler)}, max_concurrency=2)
        result = await team.run(
            [WorkItem("agent", Task(prompt, "s")) for prompt in ["slow", "bad"]], failure_mode="fail_fast"
        )
        self.assertEqual([item.status for item in result.outcomes], ["cancelled", "failed"])
        self.assertTrue(cleaned.is_set())

    async def test_caller_cancellation_propagates_after_cleanup(self):
        started, cleaned = asyncio.Event(), asyncio.Event()

        async def handler(task):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.set()

        pending = asyncio.create_task(Team({"agent": Runtime(handler)}).run([WorkItem("agent", Task("x", "s"))]))
        await asyncio.wait_for(started.wait(), 1)
        pending.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await pending
        self.assertTrue(cleaned.is_set())

    async def test_team_limits_cross_agent_concurrency(self):
        active, maximum = 0, 0

        async def handler(task):
            nonlocal active, maximum
            active += 1
            maximum = max(active, maximum)
            await asyncio.sleep(0)
            active -= 1
            return "ok"

        team = Team({"a": Runtime(handler), "b": Runtime(handler)}, max_concurrency=1)
        result = await team.run([WorkItem(agent, Task("x", "s")) for agent in ["a", "b", "a"]])
        self.assertTrue(result.succeeded)
        self.assertEqual(maximum, 1)

    async def test_unknown_and_duplicate_work_rejected_before_side_effects(self):
        calls = []

        async def handler(task):
            calls.append(task)
            return "ok"

        team = Team({"a": Runtime(handler)})
        item = WorkItem("a", Task("x", "s"))
        for work in [[item, item], [item, WorkItem("missing", Task("x", "s"))]]:
            with self.assertRaises(ValueError):
                await team.run(work)
        self.assertEqual(calls, [])

    async def test_task_cap_bounds_generator_consumption(self):
        consumed = 0

        def items():
            nonlocal consumed
            while True:
                consumed += 1
                yield WorkItem("a", Task("x", "s"))

        async def handler(task):
            return "ok"

        with self.assertRaises(ValueError):
            await Team({"a": Runtime(handler)}, max_tasks=2).run(items())
        self.assertEqual(consumed, 3)

    async def test_budget_failure_has_distinct_outcome(self):
        async def handler(task):
            return "too much"

        team = Team({"a": Runtime(handler, budget=RunBudget(max_output_chars=1))})
        result = await team.run([WorkItem("a", Task("x", "s"))])
        self.assertEqual(result.outcomes[0].status, "budget_exceeded")

    async def test_empty_batch_is_successful(self):
        async def handler(task):
            return "ok"

        result = await Team({"a": Runtime(handler)}).run([])
        self.assertTrue(result.succeeded)
        self.assertEqual(result.outcomes, ())


if __name__ == "__main__":
    unittest.main()
