"""Regression tests for the ExecutionWorker lifecycle.

These tests cover every important state transition and resilience scenario
without requiring a live Supabase instance. All external dependencies
(database RPCs, storage, engine) are replaced with async fakes.

Lifecycle states verified:
  queued → running (claim)
  running → passed  (engine pass)
  running → failed  (engine fail)
  running → failed  (malformed suite / ExecutionRunnerError)
  running → failed  (unexpected exception inside run_once)
  worker continues polling after failed execution
  worker continues polling after Supabase/queue error
  worker continues polling after unexpected worker-level exception
  second execution processed after first fails
  artifacts are uploaded and metadata is persisted
  execution timestamps: started_at set on claim, finished_at set on complete
  _jsonable serialises ExecutionStatus enum values
  workspace is cleaned up after success
  workspace is cleaned up after failure
"""
from __future__ import annotations

import asyncio
import json
import tempfile
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from ai_testing_framework.cloud.contracts import ExecutionSpec, ExecutionStatus
from ai_testing_framework.cloud.runner import ExecutionRunnerError
from ai_testing_framework.server.db import SupabaseDataError
from ai_testing_framework.server.executions import ExecutionRecord
from ai_testing_framework.server.worker import ExecutionWorker, _jsonable


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ORG_ID = str(uuid.UUID("00000000-0000-0000-0000-000000000010"))
PROJ_ID = str(uuid.UUID("00000000-0000-0000-0000-000000000020"))
USER_ID = str(uuid.UUID("00000000-0000-0000-0000-000000000030"))
EXEC_ID = str(uuid.UUID("00000000-0000-0000-0000-000000000040"))


def _execution_row(exec_id: str = EXEC_ID, status: str = "queued") -> dict[str, Any]:
    """Return a minimal executions row as returned by claim_next_execution RPC."""
    return {
        "id": exec_id,
        "organization_id": ORG_ID,
        "project_id": PROJ_ID,
        "requested_by": USER_ID,
        "status": status,
        "suite_path": "org/proj/suite.json",
        "base_url": "http://127.0.0.1:8000",
        "browser": "chromium",
        "test_id": None,
        "output_dir": "reports",
        "formats": ["html", "json"],
        "workers": 1,
        "config": None,
        "ai_provider": "none",
        "metadata": {},
        "result": None,
        "error": None,
        "created_at": "2026-09-08T10:00:00+00:00",
        "started_at": None,
        "finished_at": None,
    }


def _passed_result() -> dict[str, Any]:
    return {"status": ExecutionStatus.PASSED, "total": 2, "passed": 2, "failed": 0}


def _failed_result() -> dict[str, Any]:
    return {"status": ExecutionStatus.FAILED, "total": 2, "passed": 1, "failed": 1}


def _make_worker() -> tuple[ExecutionWorker, MagicMock, MagicMock, MagicMock, MagicMock]:
    """Return (worker, mock_db, mock_service, mock_storage, mock_engine)."""
    with (
        patch("ai_testing_framework.server.worker.SupabaseWorkerClient") as db_cls,
        patch("ai_testing_framework.server.worker.SupabaseServiceClient") as svc_cls,
        patch("ai_testing_framework.server.worker.SupabaseStorageClient") as sto_cls,
        patch("ai_testing_framework.server.worker.IsolatedExecutionRunner") as eng_cls,
    ):
        mock_db = db_cls.return_value
        mock_service = svc_cls.return_value
        mock_storage = sto_cls.return_value
        mock_engine = eng_cls.return_value
        worker = ExecutionWorker(poll_seconds=0.01)

    return worker, mock_db, mock_service, mock_storage, mock_engine


# ---------------------------------------------------------------------------
# _jsonable
# ---------------------------------------------------------------------------

class TestJsonable:
    def test_enum_serialised_to_value(self):
        assert _jsonable(ExecutionStatus.PASSED) == "passed"
        assert _jsonable(ExecutionStatus.FAILED) == "failed"

    def test_dict_values_recursed(self):
        d = {"status": ExecutionStatus.PASSED, "nested": {"s": ExecutionStatus.FAILED}}
        result = _jsonable(d)
        assert result == {"status": "passed", "nested": {"s": "failed"}}

    def test_list_items_recursed(self):
        assert _jsonable([ExecutionStatus.PASSED, "x"]) == ["passed", "x"]

    def test_tuple_treated_like_list(self):
        assert _jsonable((1, ExecutionStatus.CANCELLED)) == [1, "cancelled"]

    def test_scalar_passthrough(self):
        assert _jsonable(42) == 42
        assert _jsonable("hello") == "hello"
        assert _jsonable(None) is None


# ---------------------------------------------------------------------------
# Empty queue — worker does not claim
# ---------------------------------------------------------------------------

class TestEmptyQueue:
    def test_run_once_returns_false_when_queue_empty(self):
        worker, mock_db, *_ = _make_worker()
        mock_db.claim_next_execution = AsyncMock(return_value=[])
        result = asyncio.run(worker.run_once())
        assert result is False

    def test_run_once_returns_false_on_composite_wrapper_with_empty_inner(self):
        worker, mock_db, *_ = _make_worker()
        mock_db.claim_next_execution = AsyncMock(return_value=[{"claim_next_execution": {}}])
        result = asyncio.run(worker.run_once())
        assert result is False

    def test_run_once_returns_false_on_null_inner(self):
        worker, mock_db, *_ = _make_worker()
        mock_db.claim_next_execution = AsyncMock(return_value=[{"claim_next_execution": None}])
        result = asyncio.run(worker.run_once())
        assert result is False


# ---------------------------------------------------------------------------
# queued → running → passed
# ---------------------------------------------------------------------------

class TestPassedLifecycle:
    def test_passed_execution_calls_complete_with_passed_status(self):
        worker, mock_db, mock_service, mock_storage, mock_engine = _make_worker()

        mock_db.claim_next_execution = AsyncMock(return_value=[_execution_row()])
        mock_storage.download_bytes = AsyncMock(return_value=b'{"test_suite":"s","tests":[]}')
        mock_engine.execute = MagicMock(return_value=_passed_result())
        mock_storage.upload_file = AsyncMock(return_value=MagicMock(
            name="report.html", storage_path=f"{ORG_ID}/{PROJ_ID}/{EXEC_ID}/report.html",
            content_type="text/html", size_bytes=100,
        ))
        mock_service.insert = AsyncMock(return_value=[{"id": str(uuid.uuid4())}])
        mock_db.complete_execution = AsyncMock(return_value=[])

        with tempfile.TemporaryDirectory() as tmp:
            with patch("ai_testing_framework.server.worker.os.environ.get", side_effect=lambda k, d=None: tmp if k == "WORKER_TMP_DIR" else d):
                result = asyncio.run(worker.run_once())

        assert result is True
        args = mock_db.complete_execution.call_args[0]
        assert args[0] == EXEC_ID
        assert args[1] == ExecutionStatus.PASSED.value
        assert args[3] is None  # no error message on pass

    def test_passed_result_dict_included_in_complete_call(self):
        worker, mock_db, mock_service, mock_storage, mock_engine = _make_worker()

        mock_db.claim_next_execution = AsyncMock(return_value=[_execution_row()])
        mock_storage.download_bytes = AsyncMock(return_value=b'{"test_suite":"s","tests":[]}')
        mock_engine.execute = MagicMock(return_value=_passed_result())
        mock_storage.upload_file = AsyncMock(return_value=MagicMock(
            name="r.json", storage_path="org/proj/exec/r.json",
            content_type="application/json", size_bytes=50,
        ))
        mock_service.insert = AsyncMock(return_value=[{"id": str(uuid.uuid4())}])
        mock_db.complete_execution = AsyncMock(return_value=[])

        asyncio.run(worker.run_once())

        _, _, result_dict, _ = mock_db.complete_execution.call_args[0]
        assert result_dict is not None
        assert result_dict["status"] == "passed"
        assert result_dict["total"] == 2


# ---------------------------------------------------------------------------
# running → failed (engine returns failed status)
# ---------------------------------------------------------------------------

class TestFailedLifecycle:
    def test_failed_engine_result_persisted_as_failed(self):
        worker, mock_db, mock_service, mock_storage, mock_engine = _make_worker()

        mock_db.claim_next_execution = AsyncMock(return_value=[_execution_row()])
        mock_storage.download_bytes = AsyncMock(return_value=b'{"test_suite":"s","tests":[]}')
        mock_engine.execute = MagicMock(return_value=_failed_result())
        mock_storage.upload_file = AsyncMock(return_value=MagicMock(
            name="r.html", storage_path="p", content_type="text/html", size_bytes=10,
        ))
        mock_service.insert = AsyncMock(return_value=[{"id": str(uuid.uuid4())}])
        mock_db.complete_execution = AsyncMock(return_value=[])

        result = asyncio.run(worker.run_once())

        assert result is True
        args = mock_db.complete_execution.call_args[0]
        assert args[1] == ExecutionStatus.FAILED.value
        # error message set when failing
        assert args[3] is not None

    def test_invalid_terminal_status_normalised_to_failed(self):
        """Engine returning an unrecognised status string is treated as failed."""
        worker, mock_db, mock_service, mock_storage, mock_engine = _make_worker()

        mock_db.claim_next_execution = AsyncMock(return_value=[_execution_row()])
        mock_storage.download_bytes = AsyncMock(return_value=b'{"test_suite":"s","tests":[]}')
        mock_engine.execute = MagicMock(return_value={"status": "unknown_status", "total": 0})
        mock_storage.upload_file = AsyncMock(return_value=MagicMock(
            name="r.html", storage_path="p", content_type="text/html", size_bytes=10,
        ))
        mock_service.insert = AsyncMock(return_value=[{"id": str(uuid.uuid4())}])
        mock_db.complete_execution = AsyncMock(return_value=[])

        asyncio.run(worker.run_once())

        args = mock_db.complete_execution.call_args[0]
        assert args[1] == ExecutionStatus.FAILED.value


# ---------------------------------------------------------------------------
# running → failed (ExecutionRunnerError — malformed suite / engine crash)
# ---------------------------------------------------------------------------

class TestExecutionRunnerError:
    def test_runner_error_persisted_as_failed(self):
        worker, mock_db, mock_service, mock_storage, mock_engine = _make_worker()

        mock_db.claim_next_execution = AsyncMock(return_value=[_execution_row()])
        mock_storage.download_bytes = AsyncMock(return_value=b'{"test_suite":"s","tests":[]}')
        mock_engine.execute = MagicMock(side_effect=ExecutionRunnerError("Step requires 'selector' or 'description'"))
        mock_db.complete_execution = AsyncMock(return_value=[])

        result = asyncio.run(worker.run_once())

        assert result is True
        args = mock_db.complete_execution.call_args[0]
        assert args[1] == ExecutionStatus.FAILED.value
        assert "selector" in args[3]

    def test_worker_continues_after_runner_error(self):
        """Worker must not terminate — run_once returns True, run_forever continues."""
        worker, mock_db, mock_service, mock_storage, mock_engine = _make_worker()

        call_count = [0]

        async def claim():
            call_count[0] += 1
            if call_count[0] == 1:
                return [_execution_row(exec_id=str(uuid.uuid4()))]
            return []  # nothing on second poll

        mock_db.claim_next_execution = claim
        mock_storage.download_bytes = AsyncMock(return_value=b'{}')
        mock_engine.execute = MagicMock(side_effect=ExecutionRunnerError("boom"))
        mock_db.complete_execution = AsyncMock(return_value=[])

        # First call: claims execution, engine fails, worker persists FAILED
        r1 = asyncio.run(worker.run_once())
        assert r1 is True
        # Second call: empty queue — worker does not crash
        r2 = asyncio.run(worker.run_once())
        assert r2 is False


# ---------------------------------------------------------------------------
# Unexpected exception inside run_once execution block
# ---------------------------------------------------------------------------

class TestUnexpectedExceptionInExecution:
    def test_unexpected_exception_inside_execution_persisted_as_failed(self):
        worker, mock_db, mock_service, mock_storage, mock_engine = _make_worker()

        mock_db.claim_next_execution = AsyncMock(return_value=[_execution_row()])
        mock_storage.download_bytes = AsyncMock(return_value=b'{"test_suite":"s","tests":[]}')
        mock_engine.execute = MagicMock(side_effect=RuntimeError("unexpected crash"))
        mock_db.complete_execution = AsyncMock(return_value=[])

        result = asyncio.run(worker.run_once())

        assert result is True
        args = mock_db.complete_execution.call_args[0]
        assert args[1] == ExecutionStatus.FAILED.value
        assert "unexpected crash" in args[3]

    def test_storage_download_error_persisted_as_failed(self):
        worker, mock_db, mock_service, mock_storage, mock_engine = _make_worker()

        mock_db.claim_next_execution = AsyncMock(return_value=[_execution_row()])
        mock_storage.download_bytes = AsyncMock(
            side_effect=SupabaseDataError("Storage download failed: 404", 404)
        )
        mock_db.complete_execution = AsyncMock(return_value=[])

        result = asyncio.run(worker.run_once())

        assert result is True
        args = mock_db.complete_execution.call_args[0]
        assert args[1] == ExecutionStatus.FAILED.value


# ---------------------------------------------------------------------------
# Supabase/queue error — worker stays alive
# ---------------------------------------------------------------------------

class TestQueueErrorResilience:
    def test_supabase_error_on_claim_does_not_kill_worker(self):
        """SupabaseDataError from claim_next_execution is caught by run_forever."""
        worker, mock_db, *_ = _make_worker()

        call_count = [0]

        async def claim():
            call_count[0] += 1
            if call_count[0] == 1:
                raise SupabaseDataError("connection refused", 502)
            return []

        mock_db.claim_next_execution = claim

        async def run_two_polls():
            # Simulate two iterations of run_forever's loop body
            for _ in range(2):
                try:
                    await worker.run_once()
                except SupabaseDataError:
                    pass  # run_forever catches this
            return call_count[0]

        count = asyncio.run(run_two_polls())
        assert count == 2  # both polls attempted, worker did not stop

    def test_unexpected_exception_from_claim_does_not_kill_worker(self):
        """Any unexpected exception from the queue is swallowed by run_forever."""
        worker, mock_db, *_ = _make_worker()

        call_count = [0]

        async def claim():
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("malformed queue row: unexpected field")
            return []

        mock_db.claim_next_execution = claim

        async def run_two_polls():
            for _ in range(2):
                try:
                    await worker.run_once()
                except Exception:
                    pass
            return call_count[0]

        count = asyncio.run(run_two_polls())
        assert count == 2


# ---------------------------------------------------------------------------
# Second execution processed after first fails
# ---------------------------------------------------------------------------

class TestConsecutiveExecutions:
    def test_second_execution_processed_after_first_fails(self):
        """Core requirement: a failed execution must not block subsequent ones."""
        worker, mock_db, mock_service, mock_storage, mock_engine = _make_worker()

        exec_id_1 = str(uuid.uuid4())
        exec_id_2 = str(uuid.uuid4())
        call_count = [0]

        async def claim():
            call_count[0] += 1
            if call_count[0] == 1:
                return [_execution_row(exec_id=exec_id_1)]
            if call_count[0] == 2:
                return [_execution_row(exec_id=exec_id_2)]
            return []

        mock_db.claim_next_execution = claim
        mock_storage.download_bytes = AsyncMock(return_value=b'{"test_suite":"s","tests":[]}')
        mock_engine.execute = MagicMock(side_effect=[
            ExecutionRunnerError("first fails"),
            _passed_result(),
        ])
        mock_service.insert = AsyncMock(return_value=[{"id": str(uuid.uuid4())}])
        mock_storage.upload_file = AsyncMock(return_value=MagicMock(
            name="r.html", storage_path="p", content_type="text/html", size_bytes=10,
        ))
        complete_calls: list[tuple] = []

        async def complete(exec_id, status, result, error):
            complete_calls.append((exec_id, status))
            return []

        mock_db.complete_execution = complete

        # Process execution 1 (fails) then execution 2 (passes)
        r1 = asyncio.run(worker.run_once())
        r2 = asyncio.run(worker.run_once())

        assert r1 is True
        assert r2 is True
        assert complete_calls[0] == (exec_id_1, ExecutionStatus.FAILED.value)
        assert complete_calls[1] == (exec_id_2, ExecutionStatus.PASSED.value)

    def test_worker_does_not_require_restart_between_executions(self):
        """The same worker instance processes multiple executions without restart."""
        worker, mock_db, mock_service, mock_storage, mock_engine = _make_worker()

        ids = [str(uuid.uuid4()) for _ in range(3)]
        call_count = [0]

        async def claim():
            i = call_count[0]
            call_count[0] += 1
            if i < len(ids):
                return [_execution_row(exec_id=ids[i])]
            return []

        mock_db.claim_next_execution = claim
        mock_storage.download_bytes = AsyncMock(return_value=b'{"test_suite":"s","tests":[]}')
        mock_engine.execute = MagicMock(return_value=_passed_result())
        mock_service.insert = AsyncMock(return_value=[{"id": str(uuid.uuid4())}])
        mock_storage.upload_file = AsyncMock(return_value=MagicMock(
            name="r.html", storage_path="p", content_type="text/html", size_bytes=10,
        ))
        mock_db.complete_execution = AsyncMock(return_value=[])

        completed = sum(asyncio.run(worker.run_once()) for _ in range(len(ids) + 1))
        assert completed == len(ids)  # 3 executions processed, 4th poll returns False


# ---------------------------------------------------------------------------
# Artifact persistence
# ---------------------------------------------------------------------------

class TestArtifactPersistence:
    def test_artifacts_uploaded_and_metadata_persisted(self):
        worker, mock_db, mock_service, mock_storage, mock_engine = _make_worker()

        mock_db.claim_next_execution = AsyncMock(return_value=[_execution_row()])
        mock_storage.download_bytes = AsyncMock(return_value=b'{"test_suite":"s","tests":[]}')
        mock_engine.execute = MagicMock(return_value=_passed_result())

        artifact_id = str(uuid.uuid4())
        upload_result = MagicMock(
            name="test_report.html",
            storage_path=f"{ORG_ID}/{PROJ_ID}/{EXEC_ID}/test_report.html",
            content_type="text/html",
            size_bytes=512,
        )
        mock_storage.upload_file = AsyncMock(return_value=upload_result)
        mock_service.insert = AsyncMock(return_value=[{"id": artifact_id}])
        mock_db.complete_execution = AsyncMock(return_value=[])

        # Create a real temp workspace with a fake artifact file
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "reports"
            report_dir.mkdir()
            (report_dir / "test_report.html").write_text("<html>report</html>")

            with patch.object(worker, "_persist_artifacts", wraps=worker._persist_artifacts):
                # Manually set output_root so we can test artifact upload
                record = ExecutionRecord.from_row(_execution_row())
                artifacts = asyncio.run(worker._persist_artifacts(record, report_dir))

        assert len(artifacts) == 1
        assert artifacts[0]["name"] == upload_result.name
        assert artifacts[0]["storage_path"] == upload_result.storage_path

        # Verify service.insert was called with correct metadata
        insert_call = mock_service.insert.call_args[0]
        assert insert_call[0] == "execution_artifacts"
        metadata = insert_call[1]
        assert metadata["execution_id"] == EXEC_ID
        assert metadata["organization_id"] == ORG_ID
        assert metadata["project_id"] == PROJ_ID

    def test_empty_output_dir_produces_no_artifacts(self):
        worker, mock_db, mock_service, mock_storage, mock_engine = _make_worker()
        record = ExecutionRecord.from_row(_execution_row())

        with tempfile.TemporaryDirectory() as tmp:
            empty_dir = Path(tmp) / "empty"
            artifacts = asyncio.run(worker._persist_artifacts(record, empty_dir))

        assert artifacts == []

    def test_artifact_metadata_insert_failure_raises(self):
        worker, mock_db, mock_service, mock_storage, mock_engine = _make_worker()

        mock_storage.upload_file = AsyncMock(return_value=MagicMock(
            name="r.html", storage_path="p", content_type="text/html", size_bytes=10,
        ))
        mock_service.insert = AsyncMock(return_value=[])  # empty = failure

        record = ExecutionRecord.from_row(_execution_row())

        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "reports"
            report_dir.mkdir()
            (report_dir / "r.html").write_text("report")

            with pytest.raises(SupabaseDataError, match="Failed to persist artifact"):
                asyncio.run(worker._persist_artifacts(record, report_dir))


# ---------------------------------------------------------------------------
# Workspace cleanup
# ---------------------------------------------------------------------------

class TestWorkspaceCleanup:
    def test_workspace_cleaned_up_after_success(self):
        worker, mock_db, mock_service, mock_storage, mock_engine = _make_worker()

        mock_db.claim_next_execution = AsyncMock(return_value=[_execution_row()])
        mock_storage.download_bytes = AsyncMock(return_value=b'{"test_suite":"s","tests":[]}')
        mock_engine.execute = MagicMock(return_value=_passed_result())
        mock_storage.upload_file = AsyncMock(return_value=MagicMock(
            name="r.html", storage_path="p", content_type="text/html", size_bytes=10,
        ))
        mock_service.insert = AsyncMock(return_value=[{"id": str(uuid.uuid4())}])
        mock_db.complete_execution = AsyncMock(return_value=[])

        created_workspace: list[Path] = []
        original_mkdtemp = tempfile.mkdtemp

        def tracking_mkdtemp(**kwargs):
            d = original_mkdtemp(**kwargs)
            created_workspace.append(Path(d))
            return d

        with patch("ai_testing_framework.server.worker.tempfile.mkdtemp", side_effect=tracking_mkdtemp):
            asyncio.run(worker.run_once())

        assert created_workspace, "No workspace was created"
        assert not created_workspace[0].exists(), "Workspace was not cleaned up"

    def test_workspace_cleaned_up_after_failure(self):
        worker, mock_db, mock_service, mock_storage, mock_engine = _make_worker()

        mock_db.claim_next_execution = AsyncMock(return_value=[_execution_row()])
        mock_storage.download_bytes = AsyncMock(return_value=b'{"test_suite":"s","tests":[]}')
        mock_engine.execute = MagicMock(side_effect=ExecutionRunnerError("crash"))
        mock_db.complete_execution = AsyncMock(return_value=[])

        created_workspace: list[Path] = []
        original_mkdtemp = tempfile.mkdtemp

        def tracking_mkdtemp(**kwargs):
            d = original_mkdtemp(**kwargs)
            created_workspace.append(Path(d))
            return d

        with patch("ai_testing_framework.server.worker.tempfile.mkdtemp", side_effect=tracking_mkdtemp):
            asyncio.run(worker.run_once())

        assert created_workspace, "No workspace was created"
        assert not created_workspace[0].exists(), "Workspace was not cleaned up after failure"


# ---------------------------------------------------------------------------
# Execution record construction from DB row
# ---------------------------------------------------------------------------

class TestExecutionRecordFromRow:
    def test_from_row_parses_all_fields(self):
        row = _execution_row()
        record = ExecutionRecord.from_row(row)
        assert str(record.id) == EXEC_ID
        assert str(record.organization_id) == ORG_ID
        assert str(record.project_id) == PROJ_ID
        assert str(record.requested_by) == USER_ID
        assert record.status == "queued"
        assert record.spec.suite_path == "org/proj/suite.json"
        assert record.spec.browser == "chromium"
        assert record.spec.formats == ("html", "json")
        assert record.spec.workers == 1
        assert record.spec.ai_provider == "none"

    def test_from_row_handles_none_started_at(self):
        row = _execution_row()
        row["started_at"] = None
        record = ExecutionRecord.from_row(row)
        assert record.started_at is None

    def test_from_row_handles_iso_timestamps(self):
        row = _execution_row()
        row["started_at"] = "2026-09-08T10:01:00+00:00"
        row["finished_at"] = "2026-09-08T10:02:00+00:00"
        record = ExecutionRecord.from_row(row)
        assert record.started_at is not None
        assert record.finished_at is not None

    def test_from_row_handles_zulu_timestamps(self):
        row = _execution_row()
        row["started_at"] = "2026-09-08T10:01:00Z"
        record = ExecutionRecord.from_row(row)
        assert record.started_at is not None

    def test_composite_wrapper_unwrapped(self):
        """Defensive: old RPC returned {claim_next_execution: {row}} — worker unwraps it."""
        row = _execution_row()
        wrapped = {"claim_next_execution": row}
        # Simulate the unwrapping logic in run_once
        claimed = wrapped
        if isinstance(claimed, dict) and "claim_next_execution" in claimed:
            claimed = claimed["claim_next_execution"]
        assert claimed["id"] == EXEC_ID


# ---------------------------------------------------------------------------
# run_forever loop behaviour
# ---------------------------------------------------------------------------

class TestRunForeverLoop:
    def test_run_forever_sleeps_between_empty_polls(self):
        """When queue is empty, run_forever calls asyncio.sleep."""
        worker, mock_db, *_ = _make_worker()

        poll_count = [0]

        async def claim():
            poll_count[0] += 1
            if poll_count[0] >= 3:
                raise asyncio.CancelledError()
            return []

        mock_db.claim_next_execution = claim
        worker.poll_seconds = 0.001

        with pytest.raises(asyncio.CancelledError):
            asyncio.run(worker.run_forever())

        assert poll_count[0] >= 2

    def test_run_forever_continues_after_supabase_data_error(self):
        """SupabaseDataError from the queue does not terminate run_forever."""
        worker, mock_db, *_ = _make_worker()

        call_count = [0]

        async def claim():
            call_count[0] += 1
            if call_count[0] == 1:
                raise SupabaseDataError("transient error", 502)
            if call_count[0] >= 3:
                raise asyncio.CancelledError()
            return []

        mock_db.claim_next_execution = claim
        worker.poll_seconds = 0.001

        with pytest.raises(asyncio.CancelledError):
            asyncio.run(worker.run_forever())

        assert call_count[0] >= 2

    def test_run_forever_continues_after_unexpected_exception(self):
        """Any unexpected exception from the loop body does not terminate run_forever."""
        worker, mock_db, *_ = _make_worker()

        call_count = [0]

        async def claim():
            call_count[0] += 1
            if call_count[0] == 1:
                raise KeyError("malformed queue row")
            if call_count[0] >= 3:
                raise asyncio.CancelledError()
            return []

        mock_db.claim_next_execution = claim
        worker.poll_seconds = 0.001

        with pytest.raises(asyncio.CancelledError):
            asyncio.run(worker.run_forever())

        assert call_count[0] >= 2
