from fastapi.testclient import TestClient

from ai_testing_framework.server.api_keys import APIKeyPrincipal
from ai_testing_framework.server.app import app
from ai_testing_framework.server.auth import AuthenticatedUser, get_current_user
from ai_testing_framework.server.db import get_data_client
from ai_testing_framework.server.principal import ExecutionPrincipal, get_execution_principal


client = TestClient(app)

FAKE_USER = AuthenticatedUser(
    id="00000000-0000-0000-0000-000000000001",
    email="test@example.com",
    claims={"sub": "00000000-0000-0000-0000-000000000001"},
    access_token="test-token",
)
ORG_ID = "00000000-0000-0000-0000-000000000010"
PROJECT_ID = "00000000-0000-0000-000000000020"
EXECUTION_ID = "00000000-0000-0000-0000-000000000030"
KEY_ID = "00000000-0000-0000-0000-000000000040"
ARTIFACT_ID = "00000000-0000-0000-0000-000000000050"


class FakeDataClient:
    async def select(self, table, *, select="*", filters=None, order=None, limit=None):
        if table == "organizations":
            return [{"id": ORG_ID, "name": "Test Org", "slug": "test-org"}]
        if table == "projects":
            if filters and "id" in filters:
                return [{"id": PROJECT_ID, "organization_id": ORG_ID, "name": "Test Project", "slug": "test-project"}]
            assert filters == {"organization_id": f"eq.{ORG_ID}"}
            return [{"id": PROJECT_ID, "organization_id": ORG_ID, "name": "Test Project", "slug": "test-project"}]
        if table == "executions":
            return [{
                "id": EXECUTION_ID, "organization_id": ORG_ID, "project_id": PROJECT_ID,
                "requested_by": FAKE_USER.id, "status": "queued", "suite_path": "suite.json",
                "base_url": "http://127.0.0.1:8000", "browser": "chromium", "output_dir": "reports",
                "formats": ["html", "json"], "workers": 1, "config": None, "ai_provider": None,
                "metadata": {"source": "test"}, "result": None, "error": None,
            }]
        if table == "project_api_keys":
            return [{
                "id": KEY_ID, "organization_id": ORG_ID, "project_id": PROJECT_ID,
                "name": "CI", "key_prefix": "atk_live_test", "scopes": ["executions:read", "executions:write", "artifacts:read"],
                "last_used_at": None, "revoked_at": None, "created_at": "2026-09-07T10:00:00Z",
            }]
        if table == "execution_artifacts":
            return [{
                "id": ARTIFACT_ID, "execution_id": EXECUTION_ID, "name": "report.html",
                "storage_path": f"{ORG_ID}/{PROJECT_ID}/{EXECUTION_ID}/report.html",
                "content_type": "text/html", "size_bytes": 100, "created_at": "2026-09-07T10:00:00Z",
            }]
        return []

    async def insert(self, table, payload):
        if table == "organizations":
            assert payload["created_by"] == FAKE_USER.id
            return [{"id": ORG_ID, **payload}]
        if table == "projects":
            assert payload["created_by"] == FAKE_USER.id
            return [{"id": PROJECT_ID, **payload}]
        if table == "executions":
            assert payload["requested_by"] == FAKE_USER.id
            assert payload["status"] == "queued"
            return [{"id": EXECUTION_ID, **payload}]
        if table == "project_api_keys":
            assert payload["project_id"] == PROJECT_ID
            return [{
                "id": KEY_ID, "project_id": PROJECT_ID, "name": payload["name"],
                "key_prefix": payload["key_prefix"], "scopes": ["executions:read", "executions:write", "artifacts:read"],
                "last_used_at": None, "revoked_at": None, "created_at": "2026-09-07T10:00:00Z",
            }]
        return []

    async def update(self, table, filters, payload):
        return [{
            "id": KEY_ID, "project_id": PROJECT_ID, "name": "CI", "key_prefix": "atk_live_test",
            "scopes": ["executions:read", "executions:write", "artifacts:read"],
            "last_used_at": None, "revoked_at": payload.get("revoked_at"), "created_at": "2026-09-07T10:00:00Z",
        }]


app.dependency_overrides[get_current_user] = lambda: FAKE_USER
app.dependency_overrides[get_data_client] = lambda: FakeDataClient()
app.dependency_overrides[get_execution_principal] = lambda: ExecutionPrincipal(user=FAKE_USER)


def teardown_module():
    app.dependency_overrides.clear()


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "ai-testing-platform-api"


def test_ready():
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_protected_endpoint_requires_authentication():
    app.dependency_overrides.clear()
    response = client.get("/v1/me")
    assert response.status_code == 401
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    app.dependency_overrides[get_data_client] = lambda: FakeDataClient()
    app.dependency_overrides[get_execution_principal] = lambda: ExecutionPrincipal(user=FAKE_USER)


def test_me_returns_authenticated_user():
    response = client.get("/v1/me")
    assert response.status_code == 200
    assert response.json() == {"id": FAKE_USER.id, "email": FAKE_USER.email}


def test_organization_and_project_endpoints_use_authenticated_tenant_context():
    organization = client.post("/v1/organizations", json={"name": "Test Org", "slug": "test-org"})
    assert organization.status_code == 201
    assert organization.json()["created_by"] == FAKE_USER.id

    organizations = client.get("/v1/organizations")
    assert organizations.status_code == 200
    assert organizations.json()[0]["slug"] == "test-org"

    project = client.post("/v1/projects", json={"organization_id": ORG_ID, "name": "Test Project", "slug": "test-project"})
    assert project.status_code == 201
    assert project.json()["created_by"] == FAKE_USER.id

    projects = client.get("/v1/projects", params={"organization_id": ORG_ID})
    assert projects.status_code == 200
    assert projects.json()[0]["slug"] == "test-project"


def _execution_payload():
    return {
        "organization_id": ORG_ID,
        "project_id": PROJECT_ID,
        "spec": {
            "suite_path": "tests/sample_tests/test_suite.json",
            "base_url": "http://127.0.0.1:8000",
            "browser": "chromium",
            "formats": ["html", "json"],
            "workers": 1,
            "ai_provider": "none",
        },
        "metadata": {"source": "test"},
    }


def test_execution_is_persisted_as_queued():
    response = client.post("/v1/executions", json=_execution_payload())
    assert response.status_code == 202
    body = response.json()
    assert body["id"] == EXECUTION_ID
    assert body["status"] == "queued"
    assert body["requested_by"] == FAKE_USER.id
    assert body["metadata"] == {"source": "test"}


def test_execution_history_is_tenant_scoped():
    response = client.get("/v1/executions", params={"organization_id": ORG_ID})
    assert response.status_code == 200
    assert response.json()[0]["status"] == "queued"


def test_execution_detail_is_tenant_scoped():
    response = client.get(f"/v1/executions/{EXECUTION_ID}")
    assert response.status_code == 200
    assert response.json()["id"] == EXECUTION_ID


def test_execution_rejects_requested_by_impersonation():
    payload = _execution_payload()
    payload["requested_by"] = "00000000-0000-0000-0000-000000000099"
    response = client.post("/v1/executions", json=payload)
    assert response.status_code == 403


def test_execution_contract_rejects_unknown_browser():
    payload = _execution_payload()
    payload["spec"]["browser"] = "safari"
    response = client.post("/v1/executions", json=payload)
    assert response.status_code == 422


def test_execution_contract_rejects_extra_fields():
    payload = _execution_payload()
    payload["unexpected"] = True
    response = client.post("/v1/executions", json=payload)
    assert response.status_code == 422


def test_api_key_is_created_and_plaintext_is_returned_once():
    response = client.post(f"/v1/projects/{PROJECT_ID}/api-keys", json={"name": "CI"})
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == KEY_ID
    assert body["key"].startswith("atk_live_")
    assert "key_hash" not in body


def test_api_keys_are_listed_without_plaintext_secret():
    response = client.get(f"/v1/projects/{PROJECT_ID}/api-keys")
    assert response.status_code == 200
    assert response.json()[0]["key"] is None


def test_api_key_can_be_revoked():
    response = client.post(f"/v1/projects/{PROJECT_ID}/api-keys/{KEY_ID}/revoke")
    assert response.status_code == 200
    assert response.json()["revoked_at"] is not None


def test_artifact_metadata_is_listed():
    response = client.get(f"/v1/executions/{EXECUTION_ID}/artifacts")
    assert response.status_code == 200
    assert response.json()[0]["id"] == ARTIFACT_ID
