"""Tests for suite rename (PATCH) and delete (DELETE) endpoints."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi.testclient import TestClient

from ai_testing_framework.server.app import app
from ai_testing_framework.server.auth import AuthenticatedUser, get_current_user
from ai_testing_framework.server.db import SupabaseDataClient, SupabaseDataError, get_data_client

client = TestClient(app, raise_server_exceptions=False)

FAKE_USER = AuthenticatedUser(
    id="00000000-0000-0000-0000-000000000001",
    email="test@example.com",
    claims={"sub": "00000000-0000-0000-0000-000000000001"},
    access_token="test-token",
)
PROJECT_ID = "00000000-0000-0000-0000-000000000020"
SUITE_ID   = "00000000-0000-0000-0000-000000000030"
PATCH_URL  = f"/v1/projects/{PROJECT_ID}/test-suites/{SUITE_ID}"
DELETE_URL = f"/v1/projects/{PROJECT_ID}/test-suites/{SUITE_ID}"


def _mock_db(select_return=None, update_return=None):
    """Return an AsyncMock DB client pre-configured with given return values."""
    mock = AsyncMock(spec=SupabaseDataClient)
    mock.select.return_value  = select_return if select_return is not None else []
    mock.update.return_value  = update_return if update_return is not None else []
    mock._delete.return_value = None
    return mock


@pytest.fixture(autouse=True)
def auth():
    """Override both auth and DB dependencies so no env vars are needed."""
    db = _mock_db()
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    app.dependency_overrides[get_data_client]  = lambda: db
    yield db
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_data_client, None)


class TestRenameSuiteValidation:
    def test_rename_requires_auth(self):
        app.dependency_overrides.pop(get_current_user, None)
        try:
            res = client.patch(PATCH_URL, json={"name": "New Name"})
            assert res.status_code == 401
        finally:
            app.dependency_overrides[get_current_user] = lambda: FAKE_USER

    def test_rename_rejects_empty_name(self):
        res = client.patch(PATCH_URL, json={"name": ""})
        assert res.status_code == 422

    def test_rename_rejects_name_too_long(self):
        res = client.patch(PATCH_URL, json={"name": "x" * 121})
        assert res.status_code == 422

    def test_rename_rejects_extra_fields(self):
        res = client.patch(PATCH_URL, json={"name": "Valid", "unknown": "bad"})
        assert res.status_code == 422

    def test_rename_accepts_valid_name(self, auth):
        row = {
            "id": SUITE_ID, "organization_id": "00000000-0000-0000-0000-000000000010",
            "project_id": PROJECT_ID, "name": "New Name", "slug": "new-name",
            "created_by": FAKE_USER.id,
            "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
        }
        auth.update.return_value = [row]
        auth.select.return_value = [{"version": 1}]
        res = client.patch(PATCH_URL, json={"name": "New Name"})
        assert res.status_code == 200
        assert res.json()["name"] == "New Name"

    def test_rename_404_when_suite_not_found(self, auth):
        auth.update.return_value = []
        res = client.patch(PATCH_URL, json={"name": "New Name"})
        assert res.status_code == 404

    def test_rename_accepts_single_char_name(self, auth):
        row = {
            "id": SUITE_ID, "organization_id": "00000000-0000-0000-0000-000000000010",
            "project_id": PROJECT_ID, "name": "A", "slug": "a",
            "created_by": FAKE_USER.id,
            "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
        }
        auth.update.return_value = [row]
        auth.select.return_value = []
        res = client.patch(PATCH_URL, json={"name": "A"})
        assert res.status_code == 200

    def test_rename_accepts_max_length_name(self, auth):
        name = "x" * 120
        row = {
            "id": SUITE_ID, "organization_id": "00000000-0000-0000-0000-000000000010",
            "project_id": PROJECT_ID, "name": name, "slug": name,
            "created_by": FAKE_USER.id,
            "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
        }
        auth.update.return_value = [row]
        auth.select.return_value = []
        res = client.patch(PATCH_URL, json={"name": name})
        assert res.status_code == 200


class TestDeleteSuite:
    def test_delete_requires_auth(self):
        app.dependency_overrides.pop(get_current_user, None)
        try:
            res = client.delete(DELETE_URL)
            assert res.status_code == 401
        finally:
            app.dependency_overrides[get_current_user] = lambda: FAKE_USER

    def test_delete_returns_204_on_success(self, auth):
        auth.select.return_value = [{"id": SUITE_ID}]
        res = client.delete(DELETE_URL)
        assert res.status_code == 204

    def test_delete_returns_404_when_not_found(self, auth):
        auth.select.return_value = []
        res = client.delete(DELETE_URL)
        assert res.status_code == 404

    def test_delete_invalid_uuid_returns_422(self):
        res = client.delete(
            f"/v1/projects/{PROJECT_ID}/test-suites/not-a-uuid"
        )
        assert res.status_code == 422

    def test_delete_removes_versions_then_suite(self, auth):
        """Versions must be deleted before the suite itself."""
        auth.select.return_value = [{"id": SUITE_ID}]
        call_order = []
        async def track(table, filters):
            call_order.append(table)
        auth._delete.side_effect = track

        res = client.delete(DELETE_URL)
        assert res.status_code == 204
        assert call_order == ["test_suite_versions", "test_suites"]


class TestSuiteRouteContract:
    """PATCH and DELETE routes must be reachable (not 405 Method Not Allowed)."""

    def test_patch_route_accessible(self, auth):
        # A valid PATCH that hits the DB (mock returns not-found) proves route exists
        auth.update.return_value = []
        res = client.patch(PATCH_URL, json={"name": "Test"})
        # 404 (not found in DB) proves routing worked; 405 would mean route missing
        assert res.status_code != 405, "PATCH route is not registered"

    def test_delete_route_accessible(self, auth):
        auth.select.return_value = []
        res = client.delete(DELETE_URL)
        assert res.status_code != 405, "DELETE route is not registered"
