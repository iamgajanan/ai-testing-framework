from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from ai_testing_framework.cloud.contracts import ExecutionStatus
from ai_testing_framework.server.db import SupabaseDataError
from ai_testing_framework.server.worker import ExecutionWorker


ORG_ID = UUID("11111111-1111-1111-1111-111111111111")
PROJECT_ID = UUID("22222222-2222-2222-2222-222222222222")
USER_ID = UUID("33333333-3333-3333-3333-333333333333")
EXECUTION_ID = UUID("44444444-4444-4444-4444-444444444444")


class FakeDB:
    def __init__(self, rows):
        self.rows = list(rows)
        self.completed = []

    async def claim_next_execution(self):
        if not self.rows:
            return []
        return [self.rows.pop(0)]

    async def complete_execution(self, execution_id, status, result=None, error=None):
        self.completed.append((execution_id, status, result, error))
        return [{"id": execution_id, "status": status}]


class FakeStorage:
    def __init__(self, suite_bytes=b'{"test_suite":"worker"}'):
        self.suite_bytes = suite_bytes
        self.uploaded = []

    async def download_bytes(self, storage_path, bucket):
        assert bucket == "test-suites"
        return self.suite_bytes

    async def upload_file(self, path, storage_path):
        self.uploaded.append((path, storage_path))
        return SimpleNamespace(
            name=Path(path).name,
            storage_path=storage_path,
            content_type="text/plain",
            size_bytes=Path(path).stat().st_size,
        )


class FakeService:
    async def insert(self, table, payload):
        assert table == "execution_artifacts"
        return [{"id": "artifact-1", **payload}]


class FakeEngine:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.calls = 0

    def execute(self, request):
        self.calls += 1
        if self.fail:
            raise RuntimeError("synthetic execution failure")
        output_dir = Path(request.spec.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "result.txt").write_text("passed", encoding="utf-8")
        return {
            "status": ExecutionStatus.PASSED.value,
            "tests": [{"id": "T-001", "status": ExecutionStatus.PASSED.value}],
        }


def execution_row():
    return {
        "id": str(EXECUTION_ID),
        "organization_id": str(ORG_ID),
        "project_id": str(PROJECT_ID),
        "requested_by": str(USER_ID),
        "status": ExecutionStatus.QUEUED.value,
        "suite_path": "org/project/suite/v1/suite.json",
        "base_url": "https://example.com",
        "browser": "chromium",
        "workers": 1,
        "formats": ["html", "json"],
        "metadata": {},
    }


def make_worker(db, storage, engine):
    worker = ExecutionWorker.__new__(ExecutionWorker)
    worker.poll_seconds = 0.01
    worker.db = db
    worker.storage = storage
    worker.service = FakeService()
    worker.engine = engine
    return worker


def test_run_once_success_persists_result_and_artifacts(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKER_TMP_DIR", str(tmp_path))
    db = FakeDB([execution_row()])
    storage = FakeStorage()
    worker = make_worker(db, storage, FakeEngine())

    assert asyncio.run(worker.run_once()) is True

    assert len(db.completed) == 1
    execution_id, status, result, error = db.completed[0]
    assert execution_id == str(EXECUTION_ID)
    assert status == ExecutionStatus.PASSED.value
    assert error is None
    assert result["status"] == ExecutionStatus.PASSED.value
    assert result["artifacts"][0]["name"] == "result.txt"
    assert len(storage.uploaded) == 1


def test_failed_execution_does_not_stop_worker_and_next_job_can_run(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKER_TMP_DIR", str(tmp_path))
    first = execution_row()
    second = {**execution_row(), "id": "55555555-5555-5555-5555-555555555555"}
    db = FakeDB([first, second])
    storage = FakeStorage()

    failing_worker = make_worker(db, storage, FakeEngine(fail=True))
    assert asyncio.run(failing_worker.run_once()) is True
    assert db.completed[0][1] == ExecutionStatus.FAILED.value
    assert db.completed[0][3] == "synthetic execution failure"

    passing_worker = make_worker(db, storage, FakeEngine(fail=False))
    assert asyncio.run(passing_worker.run_once()) is True
    assert db.completed[1][1] == ExecutionStatus.PASSED.value
    assert len(db.completed) == 2


def test_run_once_returns_false_when_queue_is_empty():
    worker = make_worker(FakeDB([]), FakeStorage(), FakeEngine())
    assert asyncio.run(worker.run_once()) is False


def test_run_forever_survives_queue_error_and_keeps_polling():
    class QueueThenStop:
        def __init__(self):
            self.calls = 0

        async def __call__(self):
            self.calls += 1
            if self.calls == 1:
                raise SupabaseDataError("temporary queue failure")
            raise StopAsyncIteration

    worker = make_worker(FakeDB([]), FakeStorage(), FakeEngine())
    poll = QueueThenStop()
    worker.run_once = poll

    async def stop_after_retry(_seconds):
        return None

    async def run():
        with pytest.raises(StopAsyncIteration):
            await worker.run_forever()

    original_sleep = asyncio.sleep
    try:
        asyncio.sleep = stop_after_retry
        asyncio.run(run())
    finally:
        asyncio.sleep = original_sleep

    assert poll.calls == 2
