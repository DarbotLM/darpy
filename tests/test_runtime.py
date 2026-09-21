import asyncio
import unittest

from darpy.runtime import BudgetExceededError, RunBudget, Runtime, Task


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_receipt_and_original_task(self):
        seen = []

        async def handler(task):
            seen.append(task)
            return task.prompt.upper()

        task = Task("hello", "s", protocol="activity", request_id="r")
        result = await Runtime(handler).run(task)
        self.assertIs(seen[0], task)
        self.assertEqual((result.text, result.request_id, result.protocol), ("HELLO", "r", "activity"))
        self.assertGreaterEqual(result.elapsed_seconds, 0)

    async def test_concurrency_limit(self):
        active, maximum = 0, 0
        both_started, release = asyncio.Event(), asyncio.Event()

        async def handler(task):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            if active == 2:
                both_started.set()
            try:
                await release.wait()
                return task.prompt
            finally:
                active -= 1

        runtime = Runtime(handler, max_concurrency=2)
        pending = [asyncio.create_task(runtime.run(Task(str(i), "s"))) for i in range(4)]
        await asyncio.wait_for(both_started.wait(), 1)
        self.assertEqual(maximum, 2)
        release.set()
        await asyncio.gather(*pending)
        self.assertEqual(maximum, 2)
        self.assertEqual(active, 0)

    async def test_timeout_cleans_up_and_releases_slot(self):
        cleanup = asyncio.Event()

        async def handler(task):
            if task.prompt == "slow":
                try:
                    await asyncio.Event().wait()
                finally:
                    cleanup.set()
            return "ok"

        runtime = Runtime(handler, budget=RunBudget(timeout_seconds=0.02), max_concurrency=1)
        with self.assertRaises(BudgetExceededError) as error:
            await runtime.run(Task("slow", "s"))
        self.assertEqual(error.exception.limit, "time")
        self.assertTrue(cleanup.is_set())
        self.assertEqual((await runtime.run(Task("fast", "s"))).text, "ok")

    async def test_deadline_includes_runtime_queue(self):
        runtime = Runtime(lambda _: None, budget=RunBudget(timeout_seconds=0.02), max_concurrency=1)
        await runtime._slots.acquire()
        try:
            with self.assertRaises(BudgetExceededError) as error:
                await runtime.run(Task("waiting", "s"))
            self.assertEqual(error.exception.limit, "time")
        finally:
            runtime._slots.release()

    async def test_handler_timeout_is_not_runtime_deadline(self):
        async def handler(task):
            raise TimeoutError("upstream service deadline")

        with self.assertRaises(TimeoutError) as error:
            await Runtime(handler).run(Task("x", "s"))
        self.assertNotIsInstance(error.exception, BudgetExceededError)
        self.assertEqual(str(error.exception), "upstream service deadline")

    async def test_handler_failure_preserved(self):
        failure = LookupError("missing")

        async def handler(task):
            raise failure

        with self.assertRaises(LookupError) as error:
            await Runtime(handler).run(Task("x", "s"))
        self.assertIs(error.exception, failure)

    async def test_caller_cancellation_reaches_handler(self):
        started, cleaned = asyncio.Event(), asyncio.Event()

        async def handler(task):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.set()

        pending = asyncio.create_task(Runtime(handler).run(Task("x", "s")))
        await asyncio.wait_for(started.wait(), 1)
        pending.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await pending
        self.assertTrue(cleaned.is_set())

    async def test_suppressed_deadline_is_never_success(self):
        async def handler(task):
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                return "too late"

        with self.assertRaises(BudgetExceededError):
            await Runtime(handler, budget=RunBudget(timeout_seconds=0.02)).run(Task("x", "s"))

    async def test_input_limit_prevents_execution_and_counts_metadata(self):
        called = False

        async def handler(task):
            nonlocal called
            called = True
            return "x"

        runtime = Runtime(handler, budget=RunBudget(max_input_chars=10))
        with self.assertRaises(BudgetExceededError) as error:
            await runtime.run(Task("", "s", request_id="long-identifier"))
        self.assertEqual(error.exception.limit, "input")
        self.assertFalse(called)

    async def test_output_limit_and_output_type(self):
        for output, expected in [("abc", BudgetExceededError), (None, TypeError)]:

            async def handler(task):
                return output

            with self.subTest(output=output), self.assertRaises(expected):
                await Runtime(handler, budget=RunBudget(max_output_chars=2)).run(Task("x", "s"))

    async def test_runtime_rejects_cross_loop_reuse(self):
        async def handler(task):
            return "ok"

        runtime = Runtime(handler)
        await runtime.run(Task("x", "s"))
        with self.assertRaisesRegex(RuntimeError, "event loops"):
            await asyncio.to_thread(asyncio.run, runtime.run(Task("x", "s")))

    async def test_invalid_concurrency_rejected(self):
        for value in [0, -1, True, 1.5]:
            with self.assertRaises((ValueError, TypeError)):
                Runtime(lambda _: None, max_concurrency=value)


if __name__ == "__main__":
    unittest.main()
