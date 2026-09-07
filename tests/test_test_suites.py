from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from ai_testing_framework.server.app import app
from ai_testing_framework.server.auth import AuthenticatedUser, get_current_user
from ai_testing_framework.server.db import get_data_client
from ai_testing_framework.server.storage import StoredArtifact


class FakeDB:
    def __init__(self) -> None:
        self.org_id = uuid4()
        self.project_id = uuid4()
        self.suite_id = uuid4()
        self.version_id = uuid4()
        self.user_id = uuid4()

    async def select(self, table: str, **kwargs):
        if table == "projects":
            return [{"id": str(self.project_id), "organization_id": str(self.org_id)}]
        if table == "test_suites":
            return []
        if table == "test_suite_versions":
            return []
        return []

    async def insert(self, table: str, payload: dict):
        now = datetime.now(timezone.utc).isoformat()
        if table == "test_suites":
            return [{**payload, "id": str(self.suite_id), "created_at": now, "updated_at": now}]
        if table == "test_suite_versions":
            return [{**payload, "id": str(self.version_id), "created_at": now}]
        return []


class FakeStorage:
    async def upload_bytes(self, data, filename, storage_path, content_type, *, bucket="test-suites"):
        return StoredArtifact(filename, storage_path, content_type or "application/json", len(data))

    async def create_signed_url(self, storage_path, expires_in=3600, bucket="execution-artifacts"):
        return f"https://storage.example/signed/{storage_path}?expires={expires_in}"


def _install_overrides(fake: FakeDB):
    user = AuthenticatedUser(
        id=str(fake.user_id),
        email="user@example.com",
        claims={"sub": str(fake.user_id)},
        access_token="token",
    )
    app.dependency_overrides[get_data_client] = lambda: fake
    app.dependency_overrides[get_current_user] = lambda: user


def test_test_suite_routes_are_registered(monkeypatch):
    fake = FakeDB()
    _install_overrides(fake)
    monkeypatch.setattr("ai_testing_framework.server.test_suites.SupabaseStorageClient", FakeStorage)
    try:
        client = TestClient(app)
        target = "/v1/projects/{project_id}/test-suites"
        paths = {route.path.rstrip("/") for route in app.routes if hasattr(route, "path")}
        assert target.rstrip("/") in paths
        response = client.post(
            f"/v1/projects/{fake.project_id}/test-suites",
            files={"file": ("suite.json", b'{"tests": []}', "application/json")},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["version"] == 1
        assert body["filename"] == "suite.json"
        assert body["size_bytes"] == len(b'{"tests": []}')
        assert len(body["sha256"]) == 64
    finally:
        app.dependency_overrides.clear()


def test_test_suite_rejects_unsupported_file():
    fake = FakeDB()
    _install_overrides(fake)
    try:
        client = TestClient(app)
        response = client.post(
            f"/v1/projects/{fake.project_id}/test-suites",
            files={"file": ("suite.txt", b"tests", "text/plain")},
        )
        assert response.status_code == 415
    finally:
        app.dependency_overrides.clear()
