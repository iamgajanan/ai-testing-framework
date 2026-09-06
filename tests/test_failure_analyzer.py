"""Unit tests for Phase 7 — FailureAnalyzer."""
from __future__ import annotations

import json
from unittest.mock import Mock

import pytest

from ai_testing_framework.ai.failure_analyzer import FailureAnalyzer
from ai_testing_framework.core.models import TestResult, ValidationResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _result(status="FAIL", error="", validations=None, console=None, api=None, response=""):
    return TestResult(
        id="TC-001", name="Test", status=status, duration=1.0,
        error=error,
        validations=validations or [],
        console_errors=console or [],
        api_errors=api or [],
        response=response,
    )

def _val(type_="element_present", passed=False, reason=""):
    return ValidationResult(type=type_, passed=passed, reason=reason)


# ---------------------------------------------------------------------------
# Passing test → no analysis
# ---------------------------------------------------------------------------

class TestPassResult:
    def test_pass_returns_none_category(self):
        fa = FailureAnalyzer(provider="none")
        result = _result(status="PASS")
        diag = fa.analyze(result)
        assert diag["category"] == "none"
        assert diag["confidence"] == 1.0
        assert diag["method"] == "none"


# ---------------------------------------------------------------------------
# Heuristic — category classification
# ---------------------------------------------------------------------------

class TestHeuristicCategories:
    def _fa(self):
        return FailureAnalyzer(provider="none")

    def test_selector_error_classified(self):
        r = _result(error="Locator('#submit') not found in DOM")
        d = self._fa().analyze(r)
        assert d["category"] == "selector"
        assert d["method"] == "heuristic"

    def test_timeout_error_classified(self):
        r = _result(error="Timeout 5000ms exceeded waiting for locator")
        d = self._fa().analyze(r)
        assert d["category"] == "timeout"

    def test_network_error_classified(self):
        r = _result(error="Page.goto: net::ERR_CONNECTION_REFUSED")
        d = self._fa().analyze(r)
        assert d["category"] == "network"

    def test_javascript_error_classified(self):
        r = _result(console=["Uncaught TypeError: x is not a function"])
        d = self._fa().analyze(r)
        assert d["category"] == "javascript"

    def test_api_error_classified(self):
        r = _result(error="API response status 404 expected 200")
        d = self._fa().analyze(r)
        assert d["category"] == "api"

    def test_assertion_error_classified(self):
        r = _result(
            error="",
            validations=[_val(type_="text_contains", reason="Expected 'OpenAI' not found")]
        )
        d = self._fa().analyze(r)
        assert d["category"] == "assertion"

    def test_unknown_category_for_unrecognised_error(self):
        r = _result(error="zzz-completely-unrecognised-error-xyz")
        d = self._fa().analyze(r)
        assert d["category"] == "unknown"

    def test_root_cause_taken_from_error_first_line(self):
        r = _result(error="First line of error\nSecond line\nThird")
        d = self._fa().analyze(r)
        assert "First line" in d["root_cause"]
        assert "Second line" not in d["root_cause"]

    def test_suggested_fix_is_non_empty_for_known_categories(self):
        for error in [
            "Locator not found",
            "Timeout 5000ms exceeded",
            "net::ERR_CONNECTION_REFUSED",
            "Uncaught TypeError",
            "HTTP 500 expected 200",
        ]:
            r = _result(error=error)
            d = FailureAnalyzer(provider="none").analyze(r)
            assert d["suggested_fix"], f"No fix for error: {error!r}"

    def test_confidence_is_0_7_for_heuristic(self):
        r = _result(error="Timeout exceeded")
        d = self._fa().analyze(r)
        assert d["confidence"] == pytest.approx(0.70)

    def test_explanation_is_non_empty(self):
        r = _result(error="Timeout exceeded")
        d = self._fa().analyze(r)
        assert d["explanation"]


# ---------------------------------------------------------------------------
# Heuristic — evidence construction
# ---------------------------------------------------------------------------

class TestEvidenceBuilding:
    def test_failed_validations_included(self):
        v = _val(type_="api_response", passed=False, reason="Status mismatch")
        evidence = FailureAnalyzer._build_evidence(_result(validations=[v]))
        assert len(evidence["failed_validations"]) == 1
        assert evidence["failed_validations"][0]["reason"] == "Status mismatch"

    def test_passing_validations_excluded(self):
        good = _val(passed=True)
        bad  = _val(passed=False, reason="bad")
        evidence = FailureAnalyzer._build_evidence(_result(validations=[good, bad]))
        assert len(evidence["failed_validations"]) == 1

    def test_console_errors_capped_at_5(self):
        console = [f"Error {i}" for i in range(10)]
        evidence = FailureAnalyzer._build_evidence(_result(console=console))
        assert len(evidence["console_errors"]) == 5

    def test_page_text_snippet_capped(self):
        response = "x" * 1000
        evidence = FailureAnalyzer._build_evidence(_result(response=response))
        assert len(evidence["page_text_snippet"]) <= 600

    def test_has_screenshot_flag(self):
        r = _result()
        r.screenshot = "/tmp/shot.png"
        evidence = FailureAnalyzer._build_evidence(r)
        assert evidence["has_screenshot"] is True

    def test_no_screenshot_flag(self):
        evidence = FailureAnalyzer._build_evidence(_result())
        assert evidence["has_screenshot"] is False


# ---------------------------------------------------------------------------
# AI path (mocked OpenAI)
# ---------------------------------------------------------------------------

class TestAIPath:
    def _make_fa_with_mock_client(self, ai_response: dict):
        fa = FailureAnalyzer(provider="openai")
        fa.client = Mock()
        fa.client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content=json.dumps(ai_response)))]
        )
        return fa

    def test_ai_result_used_when_client_present(self):
        fa = self._make_fa_with_mock_client({
            "root_cause":    "Element #submit was removed",
            "category":      "selector",
            "explanation":   "The button id changed in the last deploy.",
            "suggested_fix": "Update selector to #search-btn",
            "confidence":    0.95,
        })
        d = fa.analyze(_result(error="Locator not found"))
        assert d["method"] == "ai"
        assert d["category"] == "selector"
        assert d["confidence"] == pytest.approx(0.95)
        assert "#search-btn" in d["suggested_fix"]

    def test_confidence_clamped_above_one(self):
        fa = self._make_fa_with_mock_client({
            "root_cause": "x", "category": "unknown",
            "explanation": "", "suggested_fix": "", "confidence": 1.5,
        })
        d = fa.analyze(_result())
        assert d["confidence"] <= 1.0

    def test_confidence_clamped_below_zero(self):
        fa = self._make_fa_with_mock_client({
            "root_cause": "x", "category": "unknown",
            "explanation": "", "suggested_fix": "", "confidence": -0.3,
        })
        d = fa.analyze(_result())
        assert d["confidence"] >= 0.0

    def test_ai_exception_falls_back_to_heuristic(self):
        fa = FailureAnalyzer(provider="openai")
        fa.client = Mock()
        fa.client.chat.completions.create.side_effect = RuntimeError("timeout")
        d = fa.analyze(_result(error="Timeout exceeded"))
        assert d["method"] == "heuristic"
        assert d["category"] == "timeout"

    def test_no_api_key_uses_heuristic(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        fa = FailureAnalyzer(provider="openai")
        assert fa.client is None
        d = fa.analyze(_result(error="Selector not found"))
        assert d["method"] == "heuristic"


# ---------------------------------------------------------------------------
# category_label helper
# ---------------------------------------------------------------------------

class TestCategoryLabel:
    def test_known_labels(self):
        assert FailureAnalyzer.category_label("selector")  == "Element / Selector"
        assert FailureAnalyzer.category_label("timeout")   == "Timeout"
        assert FailureAnalyzer.category_label("network")   == "Network / Connectivity"
        assert FailureAnalyzer.category_label("assertion") == "Value Assertion"
        assert FailureAnalyzer.category_label("api")       == "API / Response"

    def test_unknown_label(self):
        label = FailureAnalyzer.category_label("nonexistent")
        assert label  # not empty


# ---------------------------------------------------------------------------
# Integration: failure_analysis in TestResult model
# ---------------------------------------------------------------------------

class TestFailureAnalysisInModel:
    def test_field_defaults_to_none(self):
        r = TestResult(id="T1", name="x", status="PASS", duration=0.5)
        assert r.failure_analysis is None

    def test_field_serialised_in_to_dict(self):
        r = TestResult(id="T1", name="x", status="FAIL", duration=1.0,
                       failure_analysis={"category": "timeout", "root_cause": "boom"})
        d = r.to_dict()
        assert d["failure_analysis"]["category"] == "timeout"
