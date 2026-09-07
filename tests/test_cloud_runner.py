from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest

from ai_testing_framework.cloud.contracts import ExecutionRequest, ExecutionSpec, ExecutionStatus
from ai_testing_framework.cloud.runner import ExecutionRunnerError, IsolatedExecutionRunner, request_from_dict


def make_request() -> ExecutionRequest:
    return ExecutionRequest(
        organization_id="org-1",
        project_id="project-1",
        requested_by="user-1",
        spec=ExecutionSpec(suite_path="suite.json", output_dir="reports/job-1", formats=("json",)),
        metadata={"source": "test"},
    )


def test_request_round_trip_preserves_execution_contract() -> None:
    payload = {
        "organization_id": "org-1",
        "project_id": "project-1",
        "requested_by": "user-1",
        "metadata": {"source": "test"},
        "spec": {
            "suite_path": "suite.json",
            "base_url": "http://example.test",
            "browser": "firefox",
            "test_id": "smoke",
            "output_dir": "reports/job-1",
            "formats": ["html", "json"],
            "workers": 2,
            "config": {"timeout": 10},
            "ai_provider": "none",
        },
    }
    request = request_from_dict(payload)
    assert request.organization_id == "org-1"
    assert request.spec.browser == "firefox"
    assert request.spec.formats == ("html", "json")
    assert request.spec.workers == 2


def test_runner_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        IsolatedExecutionRunner(0)


def test_runner_parses_child_result(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = {"status": ExecutionStatus.PASSED.value, "total": 1, "passed": 1, "failed": 0}

    class FakeProcess:
        pid = 123
        returncode = 0

        def communicate(self, payload=None, timeout=None):
            assert payload
            assert timeout == 10
            json.loads(payload)
            return json.dumps(expected), ""

        def poll(self):
            return self.returncode

    def fake_popen(command, **kwargs):
        assert command[-2:] == ["-m", "ai_testing_framework.cloud.execution_process"]
        assert kwargs["text"] is True
        return FakeProcess()

    monkeypatch.setattr("ai_testing_framework.cloud.runner.subprocess.Popen", fake_popen)
    assert IsolatedExecutionRunner(10).execute(make_request()) == expected


def test_runner_surfaces_child_process_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeProcess:
        returncode = 7

        def communicate(self, payload=None, timeout=None):
            return "", "boom"

        def poll(self):
            return self.returncode

    monkeypatch.setattr("ai_testing_framework.cloud.runner.subprocess.Popen", lambda *a, **k: FakeProcess())
    with pytest.raises(ExecutionRunnerError, match="boom"):
        IsolatedExecutionRunner(10).execute(make_request())


def test_runner_surfaces_timeout_and_terminates_process(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeProcess:
        pid = 123
        returncode = None

        def communicate(self, payload=None, timeout=None):
            if payload is not None:
                raise subprocess.TimeoutExpired(["worker"], timeout)
            return "", ""

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            self.returncode = -15
            return self.returncode

    process = FakeProcess()
    monkeypatch.setattr("ai_testing_framework.cloud.runner.subprocess.Popen", lambda *a, **k: process)
    monkeypatch.setattr("ai_testing_framework.cloud.runner.os.killpg", lambda *a: None)
    with pytest.raises(ExecutionRunnerError, match="timed out"):
        IsolatedExecutionRunner(10).execute(make_request())
