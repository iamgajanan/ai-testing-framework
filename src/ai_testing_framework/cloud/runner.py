from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from dataclasses import asdict
from typing import Any

from .contracts import ExecutionRequest, ExecutionSpec, ExecutionStatus


class ExecutionRunnerError(RuntimeError):
    """Raised when an isolated execution cannot be started or completed."""


class IsolatedExecutionRunner:
    """Run one SaaS execution in a killable child process.

    The existing engine remains unchanged. The SaaS worker gets process-level
    isolation and a hard wall-clock timeout; the container is the next layer of
    isolation when deployed in production.
    """

    def __init__(self, timeout_seconds: float | None = None) -> None:
        self.timeout_seconds = timeout_seconds or float(os.environ.get("EXECUTION_TIMEOUT_SECONDS", "900"))
        if self.timeout_seconds <= 0:
            raise ValueError("Execution timeout must be greater than zero")

    def execute(self, request: ExecutionRequest) -> dict[str, Any]:
        payload = json.dumps(_request_to_dict(request), separators=(",", ":"))
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        command = [sys.executable, "-m", "ai_testing_framework.cloud.execution_process"]
        kwargs: dict[str, Any] = {
            "input": payload,
            "text": True,
            "capture_output": True,
            "timeout": self.timeout_seconds,
            "env": env,
        }
        if os.name != "nt":
            kwargs["start_new_session"] = True

        try:
            completed = subprocess.run(command, **kwargs)
        except subprocess.TimeoutExpired as exc:
            raise ExecutionRunnerError(
                f"Execution timed out after {self.timeout_seconds:.0f} seconds"
            ) from exc
        except OSError as exc:
            raise ExecutionRunnerError(f"Unable to start execution process: {exc}") from exc

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "execution process failed").strip()
            raise ExecutionRunnerError(detail[-4000:])
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ExecutionRunnerError("Execution process returned invalid JSON") from exc
        if not isinstance(result, dict):
            raise ExecutionRunnerError("Execution process returned an invalid result")
        return result


def terminate_process_group(process: subprocess.Popen[Any]) -> None:
    """Best-effort cleanup helper for callers managing a Popen directly."""
    if os.name != "nt":
        try:
            os.killpg(process.pid, signal.SIGTERM)
            return
        except ProcessLookupError:
            return
    try:
        process.terminate()
    except ProcessLookupError:
        pass


def _request_to_dict(request: ExecutionRequest) -> dict[str, Any]:
    return {
        "organization_id": request.organization_id,
        "project_id": request.project_id,
        "requested_by": request.requested_by,
        "metadata": request.metadata,
        "spec": asdict(request.spec),
    }


def request_from_dict(payload: dict[str, Any]) -> ExecutionRequest:
    spec_data = payload.get("spec")
    if not isinstance(spec_data, dict):
        raise ValueError("Execution payload is missing spec")
    spec_data["formats"] = tuple(spec_data.get("formats") or ("html", "json"))
    spec = ExecutionSpec(**spec_data)
    return ExecutionRequest(
        organization_id=str(payload["organization_id"]),
        project_id=str(payload["project_id"]),
        requested_by=payload.get("requested_by"),
        spec=spec,
        metadata=payload.get("metadata") or {},
    )
