"""AI-powered failure analysis — Phase 7.

When a test fails, this module inspects the available evidence (error
message, failed validations, console errors, page text) and produces a
structured diagnosis:

    {
        "root_cause":     "Selector #result not found in DOM",
        "category":       "selector",
        "explanation":    "The element #result ...",
        "suggested_fix":  "Check that the selector matches ...",
        "confidence":     0.87,
        "method":         "ai"      # ai | heuristic
    }

When OpenAI is unavailable the heuristic classifier uses pattern-matching
on the error string and produces genuinely useful output without any key.

Public API
----------
    analyzer = FailureAnalyzer(provider="openai")
    diagnosis = analyzer.analyze(result)        # TestResult → dict
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from ..core.models import TestResult

# ---------------------------------------------------------------------------
# Heuristic patterns (ordered: first match wins)
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[str, str, str, str]] = [
    (
        r"locator\(|locator\.|selector|nth\(|\.click|\.fill|\.wait_for|"
        r"no element|element not found|could not locate",
        "selector",
        "A CSS selector or locator could not find a matching element in the DOM.",
        "Verify the selector still exists in the page source. "
        "If the application changed, update the selector or enable self-healing.",
    ),
    (
        r"timeout|timed out|exceeded|waiting for",
        "timeout",
        "An action or wait condition exceeded its configured timeout.",
        "Increase the step timeout, check network latency, "
        "or add an explicit wait_for_selector before the action.",
    ),
    (
        r"net::err|connection refused|err_connection|failed to fetch|network",
        "network",
        "The browser could not reach the target URL or an API endpoint.",
        "Confirm the application is running and reachable at the configured base URL.",
    ),
    (
        r"console error|uncaught|typeerror|referenceerror|syntaxerror",
        "javascript",
        "The page produced JavaScript errors that may have broken functionality.",
        "Check the console errors section in the report and fix the JS issue "
        "in the application, or adjust the error_checks list.",
    ),
    (
        r"api|status|json|response|http \d{3}",
        "api",
        "An API or network response assertion failed.",
        "Verify the API endpoint returns the expected status code and JSON structure.",
    ),
    (
        r"expected|assert|mismatch|does not contain|not equal|wrong value|"
        r"text_contains|element_present",
        "assertion",
        "A validation assertion failed: the actual value did not match the expected value.",
        "Review the expected value in the test definition and compare it "
        "with the actual page content shown in the report.",
    ),
]

_CATEGORY_LABELS = {
    "selector":   "Element / Selector",
    "timeout":    "Timeout",
    "network":    "Network / Connectivity",
    "assertion":  "Value Assertion",
    "javascript": "JavaScript Error",
    "api":        "API / Response",
    "unknown":    "Unknown",
    "none":       "—",
}

_SYSTEM_PROMPT = """\
You are a senior QA engineer analysing a failing automated browser test.
Given the failure evidence below, produce a concise structured diagnosis.

Return ONLY valid JSON (no markdown fences) with exactly these keys:
{
  "root_cause":    "one-sentence description of the root cause",
  "category":      "selector|timeout|assertion|network|javascript|api|unknown",
  "explanation":   "2-3 sentence explanation of what went wrong and why",
  "suggested_fix": "concrete actionable suggestion to fix the test or the application",
  "confidence":    0.0 to 1.0
}
"""


class FailureAnalyzer:
    """Analyse failing TestResult objects and return structured diagnoses."""

    def __init__(self, provider: str = "none", model: str = "gpt-4o-mini") -> None:
        self.provider = provider.lower()
        self.model = model
        self.client = None
        if self.provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                from openai import OpenAI
                self.client = OpenAI(api_key=api_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, result: TestResult) -> dict[str, Any]:
        """Return a diagnosis dict for *result*.  Never raises."""
        if result.status == "PASS":
            return {
                "root_cause": "Test passed — no failure to analyse.",
                "category": "none",
                "explanation": "",
                "suggested_fix": "",
                "confidence": 1.0,
                "method": "none",
            }

        evidence = self._build_evidence(result)

        if self.client is not None:
            try:
                return self._ai_analyze(evidence)
            except Exception:
                pass  # fall through to heuristic

        return self._heuristic_analyze(evidence)

    # ------------------------------------------------------------------
    # Evidence construction
    # ------------------------------------------------------------------

    @staticmethod
    def _build_evidence(result: TestResult) -> dict[str, Any]:
        return {
            "test_id":   result.id,
            "test_name": result.name,
            "error":     result.error or "",
            "failed_validations": [
                {"type": v.type, "reason": v.reason, "actual": str(v.actual or "")}
                for v in result.validations if not v.passed
            ],
            "console_errors":   result.console_errors[:5],
            "api_errors":       result.api_errors[:5],
            "healed_selectors": result.healed_selectors,
            "page_text_snippet": (result.response or "")[:600],
            "has_screenshot":   bool(result.screenshot),
        }

    # ------------------------------------------------------------------
    # AI analysis
    # ------------------------------------------------------------------

    def _ai_analyze(self, evidence: dict[str, Any]) -> dict[str, Any]:
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": json.dumps(evidence, ensure_ascii=False)},
            ],
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
        return {
            "root_cause":    str(data.get("root_cause",    "Unknown")),
            "category":      str(data.get("category",      "unknown")),
            "explanation":   str(data.get("explanation",   "")),
            "suggested_fix": str(data.get("suggested_fix", "")),
            "confidence":    max(0.0, min(1.0, float(data.get("confidence", 0.5)))),
            "method":        "ai",
        }

    # ------------------------------------------------------------------
    # Heuristic analysis
    # ------------------------------------------------------------------

    @classmethod
    def _heuristic_analyze(cls, evidence: dict[str, Any]) -> dict[str, Any]:
        signals = " ".join([
            evidence.get("error", ""),
            " ".join(v.get("reason", "") for v in evidence.get("failed_validations", [])),
            " ".join(evidence.get("console_errors", [])),
            " ".join(evidence.get("api_errors", [])),
        ]).lower()

        category    = "unknown"
        explanation = "The test failed. No specific pattern was matched."
        suggested_fix = (
            "Review the error message, failed validations, and screenshot in the report."
        )

        for pattern, cat, expl, fix in _PATTERNS:
            if re.search(pattern, signals, re.I):
                category      = cat
                explanation   = expl
                suggested_fix = fix
                break

        error = evidence.get("error", "").strip()
        root_cause = error.split("\n")[0][:200] if error else "See failed validations."

        failed = evidence.get("failed_validations", [])
        if failed and category == "assertion":
            reasons = "; ".join(v.get("reason", "") for v in failed[:2])
            root_cause = reasons[:200] or root_cause

        return {
            "root_cause":    root_cause,
            "category":      category,
            "explanation":   explanation,
            "suggested_fix": suggested_fix,
            "confidence":    0.70,
            "method":        "heuristic",
        }

    @staticmethod
    def category_label(category: str) -> str:
        return _CATEGORY_LABELS.get(category, "Unknown")
