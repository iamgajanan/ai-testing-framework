from fastapi.testclient import TestClient

from ai_testing_framework.server.app import app
from ai_testing_framework.server.auth import AuthenticatedUser, get_current_user
from ai_testing_framework.server.db import get_data_client


client = TestClient(app)


FAKE_USER = AuthenticatedUser(
    id="00000000-0000-0000-0000-000000000001",
    email="test@example.com",
    claims={"sub": "00000000-0000-0000-0000-000000000001"},
    access_token="test-token",
)


class FakeDataClient:
    async def select(self, table, *, select="*", filters=None, order=None):
        if table == "organizations":
            return [{"id": "00000000-0000-0000-0000-000000000010", "name": "Test Org", "slug": "test-org"}]
        if table == "projects":
            assert filters == {"organization_id": "eq.00000000-0000-0000-0000-000000000010"}
            return [{"id": "00000000-0000-0000-0000-000000000020", "name": "Test Project", "slug": "test-project"}]
        return []

    async def insert(self, table, payload):
        if table == "organizations":
            assert payload["created_by"] == FAKE_USER.id
            return [{"id": "00000000-0000-0000-0000-000000000010", **payload}]
        if table == "projects":
            assert payload["created_by"] == FAKE_USER.id
            return [{"id": "00000000-0000-0000-0000-000000000020", **payload}]
        return []


app.dependency_overrides[get_current_user] = lambda: FAKE_USER
app.dependency_overrides[get_data_client] = lambda: FakeDataClient()


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

    project = client.post(
        "/v1/projects",
        json={
            "organization_id": "00000000-0000-0000-0000-000000000010",
            "name": "Test Project",
            "slug": "test-project",
        },
    )
    assert project.status_code == 201
    assert project.json()["created_by"] == FAKE_USER.id

    projects = client.get(
        "/v1/projects",
        params={"organization_id": "00000000-0000-0000-0000-000000000010"},
    )
    assert projects.status_code == 200
    assert projects.json()[0]["slug"] == "test-project"


def test_execution_contract_is_accepted_for_authenticated_user():
    response = client.post(
        "/v1/executions",
        json={
            "organization_id": "org-test",
            "project_id": "project-test",
            "requested_by": "user-test",
            "spec": {
                "suite_path": "tests/sample_tests/test_suite.json",
                "base_url": "http://127.0.0.1:8000",
                "browser": "chromium",
                "formats": ["html", "json"],
                "workers": 1,
                "ai_provider": "none",
            },
        },
    )
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"


def test_execution_contract_rejects_unknown_browser():
    response = client.post(
        "/v1/executions",
        json={
            "organization_id": "org-test",
            "project_id": "project-test",
            "spec": {"suite_path": "suite.json", "browser": "safari"},
        },
    )
    assert response.status_code == 422


def test_execution_contract_rejects_extra_fields():
    response = client.post(
        "/v1/executions",
        json={
            "organization_id": "org-test",
            "project_id": "project-test",
            "unexpected": True,
            "spec": {"suite_path": "suite.json"},
        },
    )
    assert response.status_code == 422
