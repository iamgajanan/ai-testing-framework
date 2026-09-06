"""Unit tests for Phase 7 — min_confidence threshold on ai_semantic validations."""
from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from ai_testing_framework.core.test_runner import _validate
from ai_testing_framework.core.models import Validation, ValidationResult
from ai_testing_framework.validators.ai_validator import AIValidator


def _ai(pass_: bool, confidence: float) -> AIValidator:
    ai = AIValidator(provider="none")
    ai.validate_response = lambda *a, **kw: {
        "pass": pass_, "reason": "test", "confidence": confidence
    }
    return ai


def _val(min_conf=None):
    return Validation(
        type="ai_semantic",
        expected="something",
        prompt="check this",
        min_confidence=min_conf,
    )


class TestMinConfidence:
    def test_no_min_confidence_passes_normally(self):
        ai = _ai(pass_=True, confidence=0.5)
        result = _validate(ai, None, _val(min_conf=None), "response")
        assert result.passed is True

    def test_above_threshold_passes(self):
        ai = _ai(pass_=True, confidence=0.85)
        result = _validate(ai, None, _val(min_conf=0.80), "response")
        assert result.passed is True

    def test_below_threshold_fails_even_when_ai_says_pass(self):
        ai = _ai(pass_=True, confidence=0.55)
        result = _validate(ai, None, _val(min_conf=0.80), "response")
        assert result.passed is False
        assert "confidence" in result.reason.lower() or "55%" in result.reason

    def test_ai_fail_stays_fail_regardless_of_threshold(self):
        ai = _ai(pass_=False, confidence=0.95)
        result = _validate(ai, None, _val(min_conf=0.50), "response")
        assert result.passed is False

    def test_exactly_at_threshold_passes(self):
        ai = _ai(pass_=True, confidence=0.80)
        result = _validate(ai, None, _val(min_conf=0.80), "response")
        assert result.passed is True

    def test_confidence_stored_in_result(self):
        ai = _ai(pass_=True, confidence=0.75)
        result = _validate(ai, None, _val(min_conf=None), "response")
        assert result.confidence == pytest.approx(0.75)

    def test_reason_mentions_threshold_when_below(self):
        ai = _ai(pass_=True, confidence=0.40)
        result = _validate(ai, None, _val(min_conf=0.70), "response")
        assert "70%" in result.reason or "required" in result.reason.lower()


# ---------------------------------------------------------------------------
# JSON parser reads min_confidence
# ---------------------------------------------------------------------------

class TestMinConfidenceParsed:
    def test_json_parser_reads_min_confidence(self):
        import json, tempfile
        from pathlib import Path
        from ai_testing_framework.parsers.json_parser import JSONParser

        suite_data = {
            "test_suite": "Test",
            "tests": [{
                "id": "T1", "name": "t", "url": "/",
                "steps": [],
                "validations": [{
                    "type": "ai_semantic",
                    "expected": "x",
                    "min_confidence": 0.85,
                }],
                "error_checks": [],
            }],
        }
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump(suite_data, f)
            tmp = f.name

        suite = JSONParser().parse(tmp)
        val = suite.tests[0].validations[0]
        assert val.min_confidence == pytest.approx(0.85)
