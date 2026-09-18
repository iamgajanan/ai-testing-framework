"""Tests for execution cancel and retry endpoints."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from ai_testing_framework.server.app import app
from ai_testing_framework.server.auth import AuthenticatedUser, get_current_user

client = TestClient(app, raise_server_exceptions=False)

USER_ID = "00000000-0000-0000-0000-000000000001"
ORG_ID  = "00000000-0000-0000-0000-000000000010"
PROJ_ID = "00000000-0000-0000-0000-000000000020"
EXEC_ID = "00000000-0000-0000-0000-000000000040"

FAKE_USER = AuthenticatedUser(
    id=USER_ID, email="test@example.com",
    claims={"sub": USER_ID}, access_token="tok",
)

def _exec_row(status="queued"):
    return {
        "id": EXEC_ID, "organization_id": ORG_ID, "project_id": PROJ_ID,
        "requested_by": USER_ID, "status": status,
        "suite_path": "org/proj/suite.json", "base_url": "http://example.com",
        "browser": "chromium", "test_id": None, "output_dir": "reports",
        "formats": ["html","json"], "workers": 1, "config": None,
        "ai_provider": "none", "result": None, "error": None,
        "created_at": "2026-01-01T00:00:00Z",
        "started_at": None, "finished_at": None,
    }

@pytest.fixture(autouse=True)
def auth():
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    yield
    app.dependency_overrides.pop(get_current_user, None)


class TestCancelExecution:
    def _cancel(self, exec_id=EXEC_ID):
        return client.post(f"/v1/executions/{exec_id}/cancel")

    def test_requires_auth(self):
        app.dependency_overrides.pop(get_current_user, None)
        try:
            res = self._cancel()
            assert res.status_code == 401
        finally:
            app.dependency_overrides[get_current_user] = lambda: FAKE_USER

    def test_cancel_queued_returns_cancelled(self):
        with patch("ai_testing_framework.server.app.SupabaseServiceClient") as M:
            M.return_value.update = AsyncMock(return_value=[{**_exec_row(), "status": "cancelled"}])
            res = self._cancel()
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "cancelled"
        assert body["id"] == EXEC_ID

    def test_cancel_already_running_returns_409(self):
        with patch("ai_testing_framework.server.app.SupabaseServiceClient") as M:
            # update returns [] = no row matched (already running/done)
            M.return_value.update = AsyncMock(return_value=[])
            res = self._cancel()
        assert res.status_code == 409

    def test_cancel_invalid_uuid_returns_422(self):
        res = client.post("/v1/executions/not-a-uuid/cancel")
        assert res.status_code == 422

    def test_cancel_calls_update_with_queued_filter(self):
        """Update must only match rows where status='queued' to prevent
        cancelling a running execution."""
        with patch("ai_testing_framework.server.app.SupabaseServiceClient") as M:
            M.return_value.update = AsyncMock(return_value=[{**_exec_row(), "status": "cancelled"}])
            self._cancel()
            call_filters = M.return_value.update.call_args[0][1]
        assert "eq.queued" in str(call_filters)

    def test_cancel_sets_finished_at(self):
        with patch("ai_testing_framework.server.app.SupabaseServiceClient") as M:
            M.return_value.update = AsyncMock(return_value=[{**_exec_row(), "status": "cancelled"}])
            self._cancel()
            call_payload = M.return_value.update.call_args[0][2]
        assert "finished_at" in call_payload


class TestRetryExecution:
    def _retry(self, exec_id=EXEC_ID):
        return client.post(f"/v1/executions/{exec_id}/retry")

    def test_requires_auth(self):
        app.dependency_overrides.pop(get_current_user, None)
        try:
            res = self._retry()
            assert res.status_code == 401
        finally:
            app.dependency_overrides[get_current_user] = lambda: FAKE_USER

    def test_retry_failed_creates_new_queued_execution(self):
        new_id = str(uuid4())
        with patch("ai_testing_framework.server.app.SupabaseServiceClient") as M:
            M.return_value.select = AsyncMock(return_value=[_exec_row("failed")])
            M.return_value.insert = AsyncMock(return_value=[{**_exec_row("queued"), "id": new_id}])
            res = self._retry()
        assert res.status_code == 201
        assert res.json()["status"] == "queued"

    def test_retry_cancelled_creates_new_queued_execution(self):
        new_id = str(uuid4())
        with patch("ai_testing_framework.server.app.SupabaseServiceClient") as M:
            M.return_value.select = AsyncMock(return_value=[_exec_row("cancelled")])
            M.return_value.insert = AsyncMock(return_value=[{**_exec_row("queued"), "id": new_id}])
            res = self._retry()
        assert res.status_code == 201

    def test_retry_queued_returns_409(self):
        with patch("ai_testing_framework.server.app.SupabaseServiceClient") as M:
            M.return_value.select = AsyncMock(return_value=[_exec_row("queued")])
            res = self._retry()
        assert res.status_code == 409

    def test_retry_running_returns_409(self):
        with patch("ai_testing_framework.server.app.SupabaseServiceClient") as M:
            M.return_value.select = AsyncMock(return_value=[_exec_row("running")])
            res = self._retry()
        assert res.status_code == 409

    def test_retry_passed_returns_409(self):
        with patch("ai_testing_framework.server.app.SupabaseServiceClient") as M:
            M.return_value.select = AsyncMock(return_value=[_exec_row("passed")])
            res = self._retry()
        assert res.status_code == 409

    def test_retry_not_found_returns_404(self):
        with patch("ai_testing_framework.server.app.SupabaseServiceClient") as M:
            M.return_value.select = AsyncMock(return_value=[])
            res = self._retry()
        assert res.status_code == 404

    def test_retry_invalid_uuid_returns_422(self):
        res = client.post("/v1/executions/not-a-uuid/retry")
        assert res.status_code == 422

    def test_retry_preserves_browser_and_suite(self):
        new_id = str(uuid4())
        orig = _exec_row("failed")
        orig["browser"] = "firefox"
        orig["suite_path"] = "org/proj/mysuite.json"
        with patch("ai_testing_framework.server.app.SupabaseServiceClient") as M:
            M.return_value.select = AsyncMock(return_value=[orig])
            M.return_value.insert = AsyncMock(return_value=[{**_exec_row("queued"), "id": new_id}])
            self._retry()
            insert_payload = M.return_value.insert.call_args[0][1]
        assert insert_payload["browser"] == "firefox"
        assert insert_payload["suite_path"] == "org/proj/mysuite.json"
        assert insert_payload["status"] == "queued"

    def test_retry_sets_requested_by_to_current_user(self):
        new_id = str(uuid4())
        with patch("ai_testing_framework.server.app.SupabaseServiceClient") as M:
            M.return_value.select = AsyncMock(return_value=[_exec_row("failed")])
            M.return_value.insert = AsyncMock(return_value=[{**_exec_row("queued"), "id": new_id}])
            self._retry()
            insert_payload = M.return_value.insert.call_args[0][1]
        assert insert_payload["requested_by"] == USER_ID
