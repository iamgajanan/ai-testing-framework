"""Unit tests for Phase 5 reporters: HTML, JSON, PDF, and history."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from ai_testing_framework.core.models import TestResult, ValidationResult
from ai_testing_framework.reporters.html_reporter import write_html_report
from ai_testing_framework.reporters.json_reporter import write_json_report
from ai_testing_framework.reporters.pdf_reporter import write_pdf_report
from ai_testing_framework.reporters.history import append_history, flaky_tests


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _result(id="TC-001", name="Test one", status="PASS", duration=1.23,
             error="", validations=None, healed=None, console=None, api=None):
    return TestResult(
        id=id, name=name, status=status, duration=duration, error=error,
        validations=validations or [],
        healed_selectors=healed or [],
        console_errors=console or [],
        api_errors=api or [],
    )


def _val(type_="element_present", passed=True, reason="ok", confidence=None):
    return ValidationResult(type=type_, passed=passed, reason=reason, confidence=confidence)


@pytest.fixture
def tmpdir():
    with tempfile.TemporaryDirectory() as d:
        yield d


# ---------------------------------------------------------------------------
# HTML reporter
# ---------------------------------------------------------------------------

class TestHTMLReporter:
    def test_creates_file(self, tmpdir):
        results = [_result()]
        path = write_html_report(results, tmpdir, suite_name="My Suite")
        assert Path(path).exists()
        assert path.endswith(".html")

    def test_contains_suite_name(self, tmpdir):
        write_html_report([_result()], tmpdir, suite_name="Regression Suite")
        html = (Path(tmpdir) / "test_report.html").read_text()
        assert "Regression Suite" in html

    def test_pass_badge_present(self, tmpdir):
        write_html_report([_result(status="PASS")], tmpdir)
        html = (Path(tmpdir) / "test_report.html").read_text()
        assert "PASS" in html

    def test_fail_badge_present(self, tmpdir):
        write_html_report([_result(status="FAIL", error="Boom")], tmpdir)
        html = (Path(tmpdir) / "test_report.html").read_text()
        assert "FAIL" in html
        assert "Boom" in html

    def test_summary_counts(self, tmpdir):
        results = [_result(status="PASS"), _result(id="TC-002", status="FAIL")]
        write_html_report(results, tmpdir)
        html = (Path(tmpdir) / "test_report.html").read_text()
        assert "2" in html   # total
        assert "1" in html   # passed / failed

    def test_validation_rendered(self, tmpdir):
        v = _val(type_="api_response", passed=False, reason="Status mismatch", confidence=0.9)
        write_html_report([_result(validations=[v])], tmpdir)
        html = (Path(tmpdir) / "test_report.html").read_text()
        assert "api_response" in html
        assert "Status mismatch" in html
        assert "90%" in html   # confidence

    def test_healed_selectors_table(self, tmpdir):
        healed = [{"failed_selector": "#old", "healed_selector": "#new",
                   "reason": "id changed", "confidence": 0.8}]
        write_html_report([_result(healed=healed)], tmpdir)
        html = (Path(tmpdir) / "test_report.html").read_text()
        assert "#old" in html
        assert "#new" in html
        assert "id changed" in html

    def test_console_errors_rendered(self, tmpdir):
        write_html_report([_result(console=["TypeError: x is undefined"])], tmpdir)
        html = (Path(tmpdir) / "test_report.html").read_text()
        assert "TypeError" in html

    def test_xss_escaped(self, tmpdir):
        write_html_report([_result(name="<script>alert(1)</script>")], tmpdir)
        html = (Path(tmpdir) / "test_report.html").read_text()
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_no_screenshot_section_when_none(self, tmpdir):
        write_html_report([_result()], tmpdir)
        html = (Path(tmpdir) / "test_report.html").read_text()
        assert "data:image/png" not in html

    def test_empty_results(self, tmpdir):
        path = write_html_report([], tmpdir)
        html = Path(path).read_text()
        assert "0" in html  # totals show zero

    def test_pass_rate_shown(self, tmpdir):
        results = [_result(status="PASS"), _result(id="TC-002", status="PASS")]
        write_html_report(results, tmpdir)
        html = (Path(tmpdir) / "test_report.html").read_text()
        assert "100" in html   # 100% pass rate

    def test_duration_shown(self, tmpdir):
        write_html_report([_result(duration=3.75)], tmpdir)
        html = (Path(tmpdir) / "test_report.html").read_text()
        assert "3.75" in html


# ---------------------------------------------------------------------------
# JSON reporter
# ---------------------------------------------------------------------------

class TestJSONReporter:
    def test_creates_file(self, tmpdir):
        path = write_json_report([_result()], tmpdir)
        assert Path(path).exists()

    def test_structure(self, tmpdir):
        write_json_report([_result()], tmpdir, suite_name="Suite A")
        data = json.loads((Path(tmpdir) / "test_report.json").read_text())
        assert data["suite_name"] == "Suite A"
        assert data["total_tests"] == 1
        assert data["passed"] == 1
        assert data["failed"] == 0
        assert "pass_rate" in data
        assert "started_at" in data
        assert "total_duration" in data
        assert len(data["results"]) == 1

    def test_pass_rate_100(self, tmpdir):
        write_json_report([_result(status="PASS")], tmpdir)
        data = json.loads((Path(tmpdir) / "test_report.json").read_text())
        assert data["pass_rate"] == 100.0

    def test_pass_rate_zero(self, tmpdir):
        write_json_report([_result(status="FAIL")], tmpdir)
        data = json.loads((Path(tmpdir) / "test_report.json").read_text())
        assert data["pass_rate"] == 0.0

    def test_healed_selectors_in_result(self, tmpdir):
        healed = [{"failed_selector": "#a", "healed_selector": "#b",
                   "reason": "x", "confidence": 0.75}]
        write_json_report([_result(healed=healed)], tmpdir)
        data = json.loads((Path(tmpdir) / "test_report.json").read_text())
        assert data["results"][0]["healed_selectors"][0]["healed_selector"] == "#b"

    def test_empty_results(self, tmpdir):
        write_json_report([], tmpdir)
        data = json.loads((Path(tmpdir) / "test_report.json").read_text())
        assert data["total_tests"] == 0
        assert data["pass_rate"] == 0.0

    def test_total_duration_sum(self, tmpdir):
        write_json_report([_result(duration=1.0), _result(id="T2", duration=2.5)], tmpdir)
        data = json.loads((Path(tmpdir) / "test_report.json").read_text())
        assert abs(data["total_duration"] - 3.5) < 0.01


# ---------------------------------------------------------------------------
# PDF reporter
# ---------------------------------------------------------------------------

class TestPDFReporter:
    def test_creates_pdf_file(self, tmpdir):
        path = write_pdf_report([_result()], tmpdir, suite_name="PDF Test")
        assert Path(path).exists()
        assert path.endswith(".pdf")
        # PDF magic bytes
        assert Path(path).read_bytes()[:4] == b"%PDF"

    def test_pdf_with_failures(self, tmpdir):
        v = _val(type_="text_contains", passed=False, reason="not found")
        r = _result(status="FAIL", error="Element missing", validations=[v])
        path = write_pdf_report([r], tmpdir)
        assert Path(path).stat().st_size > 1000  # non-trivial file

    def test_pdf_with_healing(self, tmpdir):
        healed = [{"failed_selector": "#old", "healed_selector": "#new",
                   "reason": "Changed", "confidence": 0.9}]
        path = write_pdf_report([_result(healed=healed)], tmpdir)
        assert Path(path).exists()

    def test_pdf_multiple_tests(self, tmpdir):
        results = [
            _result(id="T1", status="PASS"),
            _result(id="T2", status="FAIL", error="boom"),
        ]
        path = write_pdf_report(results, tmpdir)
        assert Path(path).stat().st_size > 2000

    def test_pdf_empty_results(self, tmpdir):
        path = write_pdf_report([], tmpdir)
        assert Path(path).exists()


# ---------------------------------------------------------------------------
# History tracker
# ---------------------------------------------------------------------------

class TestHistory:
    def test_creates_history_file(self, tmpdir):
        append_history([_result()], tmpdir, suite_name="S1")
        assert (Path(tmpdir) / "history.json").exists()

    def test_first_entry_structure(self, tmpdir):
        append_history([_result(status="PASS")], tmpdir, suite_name="Suite")
        history = json.loads((Path(tmpdir) / "history.json").read_text())
        assert len(history) == 1
        entry = history[0]
        assert entry["suite_name"] == "Suite"
        assert entry["total"] == 1
        assert entry["passed"] == 1
        assert entry["failed"] == 0
        assert entry["pass_rate"] == 100.0
        assert "run_at" in entry
        assert len(entry["tests"]) == 1
        assert entry["tests"][0]["id"] == "TC-001"

    def test_multiple_runs_accumulate(self, tmpdir):
        for i in range(3):
            append_history([_result()], tmpdir)
        history = json.loads((Path(tmpdir) / "history.json").read_text())
        assert len(history) == 3

    def test_rolling_window_caps_at_100(self, tmpdir):
        for i in range(105):
            append_history([_result()], tmpdir)
        history = json.loads((Path(tmpdir) / "history.json").read_text())
        assert len(history) == 100

    def test_healed_count_in_entry(self, tmpdir):
        healed = [{"failed_selector": "#a", "healed_selector": "#b",
                   "reason": "x", "confidence": 0.8}]
        append_history([_result(healed=healed)], tmpdir)
        history = json.loads((Path(tmpdir) / "history.json").read_text())
        assert history[0]["tests"][0]["healed"] == 1

    def test_corrupted_history_starts_fresh(self, tmpdir):
        (Path(tmpdir) / "history.json").write_text("{{broken json{{")
        append_history([_result()], tmpdir)  # should not raise
        history = json.loads((Path(tmpdir) / "history.json").read_text())
        assert len(history) == 1


class TestFlakyDetection:
    def test_no_history_returns_empty(self, tmpdir):
        assert flaky_tests(tmpdir) == []

    def test_stable_pass_not_flaky(self, tmpdir):
        for _ in range(5):
            append_history([_result(status="PASS")], tmpdir)
        assert flaky_tests(tmpdir) == []

    def test_stable_fail_not_flaky(self, tmpdir):
        for _ in range(5):
            append_history([_result(status="FAIL")], tmpdir)
        assert flaky_tests(tmpdir) == []

    def test_mixed_results_flagged_as_flaky(self, tmpdir):
        for status in ["PASS", "FAIL", "PASS", "FAIL", "PASS"]:
            append_history([_result(status=status)], tmpdir)
        flaky = flaky_tests(tmpdir, min_runs=3)
        assert len(flaky) == 1
        assert flaky[0]["id"] == "TC-001"
        assert flaky[0]["flaky_rate"] > 0

    def test_below_min_runs_not_reported(self, tmpdir):
        append_history([_result(status="PASS")], tmpdir)
        append_history([_result(status="FAIL")], tmpdir)
        # only 2 runs, min_runs=3 → not reported
        assert flaky_tests(tmpdir, min_runs=3) == []

    def test_flaky_rate_calculation(self, tmpdir):
        # 2 PASS, 3 FAIL → 60% flaky rate
        for status in ["PASS", "PASS", "FAIL", "FAIL", "FAIL"]:
            append_history([_result(status=status)], tmpdir)
        flaky = flaky_tests(tmpdir, min_runs=3)
        assert flaky[0]["flaky_rate"] == pytest.approx(60.0)

    def test_sorted_by_flaky_rate_descending(self, tmpdir):
        """Two tests: one 80% flaky, one 20% flaky — highest first."""
        for i in range(5):
            status_a = "FAIL" if i < 4 else "PASS"   # 80% fail
            status_b = "FAIL" if i == 0 else "PASS"  # 20% fail
            append_history(
                [
                    _result(id="A", name="Test A", status=status_a),
                    _result(id="B", name="Test B", status=status_b),
                ],
                tmpdir,
            )
        flaky = flaky_tests(tmpdir, min_runs=3)
        assert flaky[0]["id"] == "A"
        assert flaky[1]["id"] == "B"
