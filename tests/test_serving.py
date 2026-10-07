from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aurora.serving import BackendResourceExhausted, BoundedPredictor, PredictionRequest, ServingFailure


def request(identifier="fixture", deadline=1., sha="a" * 64):
    return PredictionRequest(request_id=identifier, expected_model_sha256=sha, features=[0.] * 24, deadline_seconds=deadline)


class ServingTests(unittest.IsolatedAsyncioTestCase):
    async def test_queue_saturation_timeout_cancellation_and_serial_backend(self):
        entered, release = asyncio.Event(), asyncio.Event()
        active, maximum = 0, 0
        async def backend(features):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            entered.set()
            await release.wait()
            active -= 1
            return [0.] * 6
        service = BoundedPredictor("a" * 64, backend, capacity=1)
        await service.start()
        running = asyncio.create_task(service.predict(request("running")))
        await entered.wait()
        waiting = asyncio.create_task(service.predict(request("waiting", .01)))
        await asyncio.sleep(0)
        with self.assertRaisesRegex(ServingFailure, "QUEUE_SATURATED"):
            await service.predict(request("excess"))
        with self.assertRaisesRegex(ServingFailure, "DEADLINE_EXCEEDED"):
            await waiting
        running.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await running
        self.assertEqual(active, 1)  # cancellation cannot make a second owner
        release.set()
        await service.queue.join()
        result = await service.predict(request("recovered"))
        self.assertEqual(result["state_mutations"], 0)
        self.assertEqual(maximum, 1)
        self.assertEqual(service.completed_backend_calls, 2)
        await service.stop()

    async def test_stale_model_resource_failure_and_restart(self):
        calls = 0
        async def backend(features):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise BackendResourceExhausted("injected fixture, not actual GPU allocation")
            return [1.] * 6
        service = BoundedPredictor("a" * 64, backend)
        with self.assertRaisesRegex(ServingFailure, "SERVICE_NOT_READY"):
            await service.predict(request())
        await service.start()
        with self.assertRaisesRegex(ServingFailure, "STALE_MODEL"):
            await service.predict(request(sha="b" * 64))
        with self.assertRaisesRegex(ServingFailure, "BACKEND_RESOURCE_EXHAUSTED"):
            await service.predict(request())
        self.assertEqual((await service.predict(request()))["scores"], [1.] * 6)
        await service.stop()
        await service.start()
        self.assertEqual((await service.predict(request()))["scores"], [1.] * 6)
        await service.stop()

    async def test_invalid_backend_output_does_not_kill_worker(self):
        calls = 0
        async def backend(features):
            nonlocal calls
            calls += 1
            return [float("nan")] * 6 if calls == 1 else [0.] * 6
        service = BoundedPredictor("a" * 64, backend)
        await service.start()
        with self.assertRaisesRegex(ServingFailure, "BACKEND_FAILED"):
            await service.predict(request())
        self.assertEqual((await service.predict(request()))["scores"], [0.] * 6)
        await service.stop()
