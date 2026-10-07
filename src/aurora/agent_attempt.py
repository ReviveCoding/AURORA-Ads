"""Preserve actually executed traces when a resource interruption escapes agent."""
from __future__ import annotations

from copy import deepcopy

from aurora.agent import run_agent, evaluate_task


class RecordingHost:
    def __init__(self, host):
        self.original = host
        self.executed_trace = []

    def __getattr__(self, name):
        return getattr(self.original, name)

    def call(self, name, arguments):
        response = self.original.call(name, arguments)
        self.executed_trace.append(deepcopy({"name": name, "arguments": arguments, "response": response}))
        return response


def recorded_attempt(task, host, generator) -> tuple[dict, dict | None]:
    """No retry, gold change or silent drop; partial attempts are actual failures.

    Only the attempted task is evaluated. Unattempted tasks must remain missing,
    and cannot enter a complete-roster matched comparison. Normal frozen metric
    definitions and host side effects are unchanged.
    """
    recording = RecordingHost(host)
    start_record = len(generator.measurements)
    try:
        return run_agent(task, recording, generator), None
    except Exception as error:
        diagnostic = {"type": type(error).__name__, "message": str(error)[:1000]}
        result = evaluate_task(task, host, recording.executed_trace, None, diagnostic["type"] + ":" + diagnostic["message"])
        result["generated_tokens"] = sum(item["completion_tokens"] for item in generator.measurements[start_record:])
        result["interrupted_after_actual_attempt"] = True
        return result, diagnostic
