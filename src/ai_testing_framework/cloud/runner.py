from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from dataclasses import asdict
from typing import Any

from .contracts import ExecutionRequest, ExecutionSpec


class ExecutionRunnerError(RuntimeError):
    """Raised when an isolated execution cannot be started or completed."""


class IsolatedExecutionRunner:
    """Run one SaaS execution in a killable child process.

    The existing engine remains unchanged. The SaaS worker gets process-level
    isolation and a hard wall-clock timeout; the container is the next layer of
    isolation when deployed in production.
    """

    def __init__(self, timeout_seconds: float | None = None) -> None:
        self.timeout_seconds = (
            float(os.environ.get("EXECUTION_TIMEOUT_SECONDS", "900"))
            if timeout_seconds is None
            else float(timeout_seconds)
        )
        if self.timeout_seconds <= 0:
            raise ValueError("Execution timeout must be greater than zero")

    def execute(self, request: ExecutionRequest) -> dict[str, Any]:
        payload = json.dumps(_request_to_dict(request), separators=(",", ":"))
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        command = [sys.executable, "-m", "ai_testing_framework.cloud.execution_process"]
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            start_new_session=os.name != "nt",
        )
        try:
            stdout, stderr = process.communicate(payload, timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            _terminate_process_tree(process)
            process.communicate()
            raise ExecutionRunnerError(
                f"Execution timed out after {self.timeout_seconds:.0f} seconds"
            ) from exc
        except OSError as exc:
            _terminate_process_tree(process)
            process.communicate()
            raise ExecutionRunnerError(f"Execution process failed: {exc}") from exc

        if process.returncode != 0:
            detail = (stderr or stdout or "execution process failed").strip()
            raise ExecutionRunnerError(detail[-4000:])
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise ExecutionRunnerError("Execution process returned invalid JSON") from exc
        if not isinstance(result, dict):
            raise ExecutionRunnerError("Execution process returned an invalid result")
        return result


def _terminate_process_tree(process: subprocess.Popen[Any]) -> None:
    """Terminate the child and its descendants on timeout/fatal process errors."""
    if process.poll() is not None:
        return
    if os.name != "nt":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    else:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                return
        else:
            process.kill()
        process.wait(timeout=5)


def _request_to_dict(request: ExecutionRequest) -> dict[str, Any]:
    return {
        "organization_id": request.organization_id,
        "project_id": request.project_id,
        "requested_by": request.requested_by,
        "metadata": request.metadata,
        "spec": asdict(request.spec),
    }


def request_from_dict(payload: dict[str, Any]) -> ExecutionRequest:
    spec_data = dict(payload.get("spec") or {})
    if not spec_data:
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
