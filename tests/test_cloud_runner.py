from __future__ import annotations

import json
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

    def fake_run(command, **kwargs):
        assert command[-2:] == ["-m", "ai_testing_framework.cloud.execution_process"]
        assert kwargs["text"] is True
        assert kwargs["capture_output"] is True
        json.loads(kwargs["input"])
        return SimpleNamespace(returncode=0, stdout=json.dumps(expected), stderr="")

    monkeypatch.setattr("ai_testing_framework.cloud.runner.subprocess.run", fake_run)
    assert IsolatedExecutionRunner(10).execute(make_request()) == expected


def test_runner_surfaces_child_process_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command, **kwargs):
        return SimpleNamespace(returncode=7, stdout="", stderr="boom")

    monkeypatch.setattr("ai_testing_framework.cloud.runner.subprocess.run", fake_run)
    with pytest.raises(ExecutionRunnerError, match="boom"):
        IsolatedExecutionRunner(10).execute(make_request())


def test_runner_surfaces_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command, **kwargs):
        raise __import__("subprocess").TimeoutExpired(command, 10)

    monkeypatch.setattr("ai_testing_framework.cloud.runner.subprocess.run", fake_run)
    with pytest.raises(ExecutionRunnerError, match="timed out"):
        IsolatedExecutionRunner(10).execute(make_request())
