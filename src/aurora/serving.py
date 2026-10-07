"""Bounded, read-only prediction service; economic mutation stays in the host."""
from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass
from typing import Awaitable, Callable

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1, max_length=128)
    expected_model_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    features: list[float] = Field(min_length=24, max_length=24)
    deadline_seconds: float = Field(gt=0, le=5)

    @field_validator("features")
    @classmethod
    def finite_features(cls, value: list[float]) -> list[float]:
        if not all(math.isfinite(item) for item in value):
            raise ValueError("Finite public feature vector required")
        return value


class ServingFailure(RuntimeError):
    def __init__(self, reason: str, http_status: int):
        super().__init__(reason)
        self.reason = reason
        self.http_status = http_status


class BackendResourceExhausted(RuntimeError):
    """Backend maps an actual OOM to this error; fixtures cannot prove GPU OOM."""


class BackendEnvelopeLost(RuntimeError):
    """Latched hardware envelope violation; never silently resume GPU requests."""


@dataclass
class _Queued:
    request: PredictionRequest
    admitted_at: float
    future: asyncio.Future


class BoundedPredictor:
    """One backend call at a time; capacity is active1 + queued ``capacity``.

    Cancelling a running request does not free backend concurrency until that
    call really finishes. Inference is read-only: cancellation/retry cannot
    create or settle a budget reservation. Shutdown drains accepted requests.
    """
    def __init__(self, model_sha256: str, backend: Callable[[list[float]], Awaitable[list[float]]], *, capacity: int = 16):
        if capacity <= 0 or len(model_sha256) != 64 or any(character not in "0123456789abcdef" for character in model_sha256):
            raise ValueError("Positive bounded queue and exact model SHA required")
        self.model_sha256 = model_sha256
        self.backend = backend
        self.queue: asyncio.Queue[_Queued | None] = asyncio.Queue(capacity)
        self.worker: asyncio.Task | None = None
        self.accepting = False
        self.completed_backend_calls = 0

    async def start(self) -> None:
        if self.worker is not None:
            raise RuntimeError("Already started")
        self.accepting = True
        self.worker = asyncio.create_task(self._work())

    async def stop(self) -> None:
        self.accepting = False
        if self.worker is not None:
            await self.queue.put(None)
            await self.worker
            self.worker = None

    async def predict(self, request: PredictionRequest) -> dict:
        if not self.accepting:
            raise ServingFailure("SERVICE_NOT_READY", 503)
        if request.expected_model_sha256 != self.model_sha256:
            raise ServingFailure("STALE_MODEL", 409)
        queued = _Queued(request, time.perf_counter(), asyncio.get_running_loop().create_future())
        try:
            self.queue.put_nowait(queued)
        except asyncio.QueueFull as error:
            raise ServingFailure("QUEUE_SATURATED", 503) from error
        try:
            return await asyncio.wait_for(queued.future, request.deadline_seconds)
        except TimeoutError as error:
            raise ServingFailure("DEADLINE_EXCEEDED", 504) from error

    async def _work(self) -> None:
        while True:
            item = await self.queue.get()
            try:
                if item is None:
                    return
                if item.future.done():
                    continue
                begin = time.perf_counter()
                try:
                    scores = await self.backend(item.request.features)
                    self.completed_backend_calls += 1
                    if len(scores) != 6 or not all(math.isfinite(score) for score in scores):
                        raise ValueError("Invalid six-candidate model output")
                    candidate = max(range(6), key=lambda index: scores[index])
                    response = {"request_id": item.request.request_id, "model_sha256": self.model_sha256, "evidence_domain": "S1_SYNTHETIC_OBSERVED_VALUE_SURROGATE", "scores": scores, "provisional_candidate_index": candidate, "queue_seconds": begin - item.admitted_at, "backend_seconds": time.perf_counter() - begin, "feature_to_provisional_decision_seconds": time.perf_counter() - item.admitted_at, "decision_scope": "frozen mean-head ranking only; not authorized, host-guarded or adaptive campaign decision", "state_mutations": 0}
                    if not item.future.done():
                        item.future.set_result(response)
                except Exception as error:
                    reason = "RESOURCE_ENVELOPE_LOST" if isinstance(error, BackendEnvelopeLost) else "BACKEND_RESOURCE_EXHAUSTED" if isinstance(error, BackendResourceExhausted) else "BACKEND_FAILED"
                    failure = ServingFailure(reason, 503)
                    if not item.future.done():
                        item.future.set_exception(failure)
            finally:
                self.queue.task_done()


def create_app(service: BoundedPredictor) -> FastAPI:
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def lifespan(app):
        await service.start()
        try:
            yield
        finally:
            await service.stop()
    app = FastAPI(lifespan=lifespan)
    @app.get("/health")
    async def health():
        return {"ready": service.accepting, "model_sha256": service.model_sha256, "queued": service.queue.qsize(), "queue_capacity": service.queue.maxsize}
    @app.post("/predict")
    async def predict(request: PredictionRequest):
        try:
            return await service.predict(request)
        except ServingFailure as error:
            raise HTTPException(status_code=error.http_status, detail=error.reason) from error
    return app
