"""Tests for POST /v1/generate — natural-language test suite generation."""
from __future__ import annotations

import json
import pathlib
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from ai_testing_framework.server.app import app
from ai_testing_framework.server.auth import AuthenticatedUser, get_current_user

client = TestClient(app, raise_server_exceptions=False)

FAKE_USER = AuthenticatedUser(
    id="00000000-0000-0000-0000-000000000001",
    email="test@example.com",
    claims={"sub": "00000000-0000-0000-0000-000000000001"},
    access_token="test-token",
)
ORG_ID = "00000000-0000-0000-0000-000000000010"
PROJECT_ID = "00000000-0000-0000-0000-000000000020"

VALID_PAYLOAD = {
    "project_id": PROJECT_ID,
    "organization_id": ORG_ID,
    "prompt": "Test the homepage and verify it loads correctly.",
    "base_url": "https://example.com",
}


@pytest.fixture(autouse=True)
def auth():
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    yield
    app.dependency_overrides.pop(get_current_user, None)


class TestGenerationValidation:
    def test_requires_authentication(self):
        app.dependency_overrides.pop(get_current_user, None)
        try:
            res = client.post("/v1/generate", json=VALID_PAYLOAD)
            assert res.status_code == 401
        finally:
            app.dependency_overrides[get_current_user] = lambda: FAKE_USER

    def test_rejects_prompt_too_short(self):
        res = client.post("/v1/generate", json={**VALID_PAYLOAD, "prompt": "too short"})
        assert res.status_code == 422

    def test_rejects_empty_base_url(self):
        res = client.post("/v1/generate", json={**VALID_PAYLOAD, "base_url": ""})
        assert res.status_code == 422

    def test_rejects_invalid_browser(self):
        res = client.post("/v1/generate", json={**VALID_PAYLOAD, "browser": "safari"})
        assert res.status_code == 422

    def test_rejects_extra_fields(self):
        res = client.post("/v1/generate", json={**VALID_PAYLOAD, "unknown_field": "bad"})
        assert res.status_code == 422

    def test_accepts_valid_firefox_browser(self):
        with patch("ai_testing_framework.server.app._TestGenerator") as M:
            M.return_value.generate.side_effect = RuntimeError("unreachable")
            res = client.post("/v1/generate", json={**VALID_PAYLOAD, "browser": "firefox"})
        assert res.status_code == 200
        assert res.json()["browser"] == "firefox"

    def test_accepts_valid_webkit_browser(self):
        with patch("ai_testing_framework.server.app._TestGenerator") as M:
            M.return_value.generate.side_effect = RuntimeError("unreachable")
            res = client.post("/v1/generate", json={**VALID_PAYLOAD, "browser": "webkit"})
        assert res.status_code == 200
        assert res.json()["browser"] == "webkit"


class TestGenerationFallback:
    """When the target URL is unreachable the endpoint must return a
    valid fallback suite — never a 5xx error."""

    def test_returns_200_when_page_unreachable(self):
        with patch("ai_testing_framework.server.app._TestGenerator") as M:
            M.return_value.generate.side_effect = RuntimeError("Connection refused")
            res = client.post("/v1/generate", json={**VALID_PAYLOAD, "base_url": "http://127.0.0.1:9999"})
        assert res.status_code == 200

    def test_fallback_suite_is_valid_json(self):
        with patch("ai_testing_framework.server.app._TestGenerator") as M:
            M.return_value.generate.side_effect = RuntimeError("Connection refused")
            res = client.post("/v1/generate", json={**VALID_PAYLOAD, "base_url": "http://127.0.0.1:9999"})
        body = res.json()
        assert "suite" in body
        assert "test_suite" in body["suite"]
        assert isinstance(body["suite"]["tests"], list)
        assert len(body["suite"]["tests"]) >= 1

    def test_fallback_test_has_required_fields(self):
        with patch("ai_testing_framework.server.app._TestGenerator") as M:
            M.return_value.generate.side_effect = RuntimeError("unreachable")
            res = client.post("/v1/generate", json={**VALID_PAYLOAD, "base_url": "http://127.0.0.1:9999"})
        for test in res.json()["suite"]["tests"]:
            assert "id" in test
            assert "name" in test
            assert "url" in test
            assert "steps" in test
            assert "validations" in test

    def test_fallback_suite_name_contains_prompt(self):
        prompt = "Test the homepage and verify it loads correctly."
        with patch("ai_testing_framework.server.app._TestGenerator") as M:
            M.return_value.generate.side_effect = RuntimeError("unreachable")
            res = client.post("/v1/generate", json={**VALID_PAYLOAD, "prompt": prompt, "base_url": "http://127.0.0.1:9999"})
        assert prompt[:30] in res.json()["suite"]["test_suite"]

    def test_response_echoes_prompt(self):
        prompt = "Test the homepage and verify it loads correctly."
        with patch("ai_testing_framework.server.app._TestGenerator") as M:
            M.return_value.generate.side_effect = RuntimeError("unreachable")
            res = client.post("/v1/generate", json={**VALID_PAYLOAD, "prompt": prompt, "base_url": "http://127.0.0.1:9999"})
        assert res.json()["prompt"] == prompt

    def test_response_echoes_base_url(self):
        with patch("ai_testing_framework.server.app._TestGenerator") as M:
            M.return_value.generate.side_effect = RuntimeError("unreachable")
            res = client.post("/v1/generate", json={**VALID_PAYLOAD, "base_url": "http://127.0.0.1:9999"})
        assert res.json()["base_url"] == "http://127.0.0.1:9999"

    def test_browser_defaults_to_chromium(self):
        with patch("ai_testing_framework.server.app._TestGenerator") as M:
            M.return_value.generate.side_effect = RuntimeError("unreachable")
            res = client.post("/v1/generate", json=VALID_PAYLOAD)
        assert res.json()["browser"] == "chromium"


class TestGenerationSuccess:
    """When the generator succeeds the suite is included in the response."""

    def _fake_generate(self, suite: dict):
        def side_effect(url, output_path, **kwargs):
            pathlib.Path(output_path).write_text(json.dumps(suite), encoding="utf-8")
        return side_effect

    def test_returns_generated_suite(self):
        suite = {
            "test_suite": "My Suite",
            "tests": [{
                "id": "GEN-001", "name": "Homepage loads", "url": "/",
                "steps": [{"action": "wait", "selector": "body"}],
                "validations": [{"type": "element_present", "selector": "h1"}],
                "error_checks": [],
            }],
        }
        with patch("ai_testing_framework.server.app._TestGenerator") as M:
            M.return_value.generate.side_effect = self._fake_generate(suite)
            res = client.post("/v1/generate", json=VALID_PAYLOAD)

        assert res.status_code == 200
        body = res.json()
        assert "suite" in body
        assert len(body["suite"]["tests"]) == 1
        assert body["suite"]["tests"][0]["id"] == "GEN-001"

    def test_suite_name_overridden_with_prompt(self):
        suite = {"test_suite": "Original Name", "tests": []}
        with patch("ai_testing_framework.server.app._TestGenerator") as M:
            M.return_value.generate.side_effect = self._fake_generate(suite)
            res = client.post("/v1/generate", json=VALID_PAYLOAD)

        # Suite name is always overridden to include the prompt
        assert "Generated:" in res.json()["suite"]["test_suite"]
