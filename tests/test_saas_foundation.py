from fastapi.testclient import TestClient

from ai_testing_framework.server.app import app


client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "ai-testing-platform-api"


def test_ready():
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_execution_contract_is_accepted_without_running_engine():
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
