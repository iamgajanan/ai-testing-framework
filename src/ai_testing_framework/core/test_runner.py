from __future__ import annotations

# This module is framework code, not a pytest test module.
__test__ = False

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..automation.network_interceptor import NetworkInterceptor
from ..automation.playwright_engine import PlaywrightEngine
from ..core.models import TestCase, TestResult, ValidationResult, TestSuite
from ..core.parallel_runner import run_parallel
from ..parsers.csv_parser import CSVParser
from ..parsers.json_parser import JSONParser
from ..parsers.md_parser import MarkdownParser
from ..parsers.xlsx_parser import XLSXParser
from ..reporters.history import append_history
from ..reporters.html_reporter import write_html_report
from ..reporters.json_reporter import write_json_report
from ..reporters.pdf_reporter import write_pdf_report
from ..validators.ai_validator import AIValidator
from ..validators.api_validator import validate_api_response
from ..validators.regex_validator import validate_regex
from ..validators.table_validator import validate_table
from ..validators.ui_validator import (
    validate_element_present,
    validate_text_contains,
    validate_url_contains,
)
from ..ai.failure_analyzer import FailureAnalyzer
from .config import load_config


class TestRunner:
    def __init__(self, config: str | dict | None = None, base_url: str = "") -> None:
        self.config = (
            load_config(config) if isinstance(config, str) or config is None else config
        )
        self.base_url = base_url
        self._build_ai_validator()

    # ------------------------------------------------------------------
    # AI provider
    # ------------------------------------------------------------------

    def _build_ai_validator(self) -> None:
        self.ai = AIValidator(self.config["ai"]["provider"], self.config["ai"]["model"])

    def set_ai_provider(self, provider: str) -> None:
        self.config["ai"]["provider"] = provider
        self._build_ai_validator()

    # ------------------------------------------------------------------
    # Suite loading
    # ------------------------------------------------------------------

    def load_suite(self, test_file: str) -> TestSuite:
        suffix = Path(test_file).suffix.lower()
        if suffix == ".json":
            return JSONParser().parse(test_file)
        if suffix in {".md", ".markdown"}:
            return MarkdownParser().parse(test_file)
        if suffix == ".csv":
            return CSVParser().parse(test_file)
        if suffix in {".xlsx", ".xlsm"}:
            return XLSXParser().parse(test_file)
        raise ValueError(
            f"Unsupported test suite format: {suffix}. "
            "Use .md, .json, .csv, .xlsx, or .xlsm"
        )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(
        self,
        test_file: str,
        browser: Optional[str] = None,
        test_id: Optional[str] = None,
        output_dir: Optional[str] = None,
        formats: Optional[list[str]] = None,
        workers: Optional[int] = None,
    ) -> list[TestResult]:
        suite      = self.load_suite(test_file)
        selected   = [t for t in suite.tests if not test_id or t.id == test_id]
        if not selected:
            raise ValueError(f"No matching test found for id={test_id!r}")

        report_dir   = output_dir or self.config["report"]["output_dir"]
        suite_name   = suite.name
        started_at   = datetime.now(timezone.utc).isoformat()
        emit_formats = formats or self.config["report"].get("formats", ["html", "json"])
        n_workers    = workers if workers is not None else self.config.get("parallel", {}).get("workers", 1)
        n_workers    = max(1, int(n_workers))

        # Build a frozen snapshot of config for worker threads.
        # Each worker constructs its own PlaywrightEngine from this snapshot;
        # no engine or browser object is shared across threads.
        run_config = dict(
            browser_name  = browser or self.config.get("browser", "chromium"),
            headless      = self.config.get("headless", True),
            timeout       = self.config.get("timeout", 30000),
            ai_provider   = self.config["ai"]["provider"],
            ai_model      = self.config["ai"]["model"],
            base_url      = self.base_url,
            report_dir    = report_dir,
            analyze_failures = self.config.get("ai", {}).get("analyze_failures", True),
        )

        def _worker(test: TestCase) -> TestResult:
            return _run_test_isolated(test, run_config)

        results = run_parallel(selected, _worker, workers=n_workers)

        # ------------------------------------------------------------------
        # Reporting (always sequential — reporters are not thread-safe)
        # ------------------------------------------------------------------
        kw = dict(suite_name=suite_name, started_at=started_at)
        if "html" in emit_formats or self.config["report"].get("html", True):
            write_html_report(results, report_dir, **kw)
        if "json" in emit_formats or self.config["report"].get("json", True):
            write_json_report(results, report_dir, **kw)
        if "pdf" in emit_formats or self.config["report"].get("pdf", False):
            try:
                write_pdf_report(results, report_dir, **kw)
            except ImportError as exc:
                print(f"Warning: PDF report skipped — {exc}")
        append_history(results, report_dir, **kw)

        return results

    # ------------------------------------------------------------------
    # Validation (used by _run_test_isolated via closure — kept on class
    # so tests can call runner._validate() directly as before)
    # ------------------------------------------------------------------

    @staticmethod
    def _has_api_candidate(responses: list, validation) -> bool:
        url    = validation.api_url or ""
        method = (validation.api_method or "").upper()
        status = validation.api_status
        for item in responses:
            actual_url   = str(item.get("url", ""))
            url_match    = (
                not url
                or (
                    url.startswith("/")
                    and (
                        actual_url.split("?", 1)[0].endswith(url)
                        or actual_url.split("?", 1)[0].endswith(url.rstrip("/"))
                    )
                )
                or url in actual_url
            )
            method_match = not method or str(item.get("method", "")).upper() == method
            status_match = status is None or int(item.get("status", -1)) == int(status)
            if url_match and method_match and status_match:
                return True
        return False

    def _validate(
        self,
        page,
        validation,
        response: str,
        interceptor: Optional[NetworkInterceptor] = None,
    ) -> ValidationResult:
        return _validate(self.ai, page, validation, response, interceptor)


# ---------------------------------------------------------------------------
# Module-level helpers (called from worker threads — no shared state)
# ---------------------------------------------------------------------------

def _validate(
    ai: AIValidator,
    page,
    validation,
    response: str,
    interceptor: Optional[NetworkInterceptor] = None,
) -> ValidationResult:
    """Pure validation dispatcher — no side-effects, safe to call from any thread."""
    kind = validation.type.lower()

    if kind == "ai_semantic":
        result = ai.validate_response(
            response, str(validation.expected or ""), validation.prompt
        )
        passed = bool(result.get("pass"))
        conf   = float(result.get("confidence", 0))
        reason = result.get("reason", "")
        min_conf = validation.min_confidence
        if passed and min_conf is not None and conf < min_conf:
            passed = False
            reason = (
                f"AI said pass but confidence {conf:.0%} < required {min_conf:.0%}. "
                + reason
            )
        return ValidationResult(kind, passed, reason, conf)

    if kind == "api_response":
        if interceptor is None:
            return ValidationResult(kind, False, "API interceptor is not available")
        passed, reason, actual = validate_api_response(
            interceptor.response_snapshot(),
            url=validation.api_url or "",
            method=validation.api_method or "",
            status=validation.api_status,
            json_path=validation.json_path or "",
            expected=validation.expected,
            body_contains=validation.body_contains or "",
        )
        return ValidationResult(kind, passed, reason, actual=actual)

    if kind == "regex":
        passed, reason = validate_regex(response, validation.pattern or "")
        return ValidationResult(kind, passed, reason, actual=response)

    if kind == "element_present":
        passed, reason = validate_element_present(page, validation.selector or "")
        return ValidationResult(kind, passed, reason)

    if kind in {"text_contains", "ui_text"}:
        if kind == "ui_text" and not validation.selector:
            passed = str(validation.expected or "").lower() in response.lower()
            return ValidationResult(kind, passed, f"Expected text: {validation.expected!r}")
        passed, reason = validate_text_contains(
            page,
            validation.selector or ".result-text, .result-container",
            str(validation.expected or ""),
            timeout=validation.timeout,
        )
        return ValidationResult(kind, passed, reason)

    if kind == "url_contains":
        passed, reason = validate_url_contains(page, str(validation.expected or ""))
        return ValidationResult(kind, passed, reason)

    if kind == "table_validation":
        passed, reason = validate_table(
            page,
            validation.selector,
            validation.expected_columns,
            validation.row_condition,
        )
        return ValidationResult(kind, passed, reason)

    raise ValueError(f"Unsupported validation type: {validation.type!r}")


def _run_test_isolated(test: TestCase, run_config: dict) -> TestResult:
    """Run a single test in a fully isolated engine.

    This function is called from worker threads.  It creates its own
    PlaywrightEngine (= its own browser process), runs the test, tears
    down the engine, and returns a plain TestResult dataclass.

    No global or shared mutable state is accessed.  The only shared
    resource is the network (the target web application) and the
    filesystem (screenshot paths, which are unique per test.id).
    """
    started    = time.perf_counter()
    validations: list[ValidationResult] = []
    error      = ""
    response   = ""
    screenshot = None
    console: list[str] = []
    api_errs: list[str] = []

    # Build an AI validator local to this thread.
    ai = AIValidator(run_config["ai_provider"], run_config["ai_model"])

    engine = PlaywrightEngine(
        browser_name=run_config["browser_name"],
        headless=run_config["headless"],
        timeout=run_config["timeout"],
        ai_provider=run_config["ai_provider"],
        ai_model=run_config["ai_model"],
    )
    engine.start()
    try:
        interceptor = NetworkInterceptor()
        assert engine.page is not None
        interceptor.attach(engine.page)

        engine.open(test.url, run_config["base_url"])
        for step in test.steps:
            engine.run_step(step)

        # Wait for async API responses before validating.
        api_validations = [v for v in test.validations if v.type.lower() == "api_response"]
        if api_validations:
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                snapshot = interceptor.response_snapshot()
                if all(
                    TestRunner._has_api_candidate(snapshot, v) for v in api_validations
                ):
                    break
                engine.page.wait_for_timeout(50)

        response = engine.response_text()

        for validation in test.validations:
            validations.append(_validate(ai, engine.page, validation, response, interceptor))

        console, api_errs = interceptor.snapshot()

        if any(c.lower() == "console_errors" for c in test.error_checks) and console:
            validations.append(
                ValidationResult("console_errors", False, f"{len(console)} console error(s)")
            )
            error = "Console errors detected"
        if any(c.lower() == "api_errors" for c in test.error_checks) and api_errs:
            validations.append(
                ValidationResult("api_errors", False, f"{len(api_errs)} network error(s)")
            )
            error = error or "API/network errors detected"

        failed = [v for v in validations if not v.passed]
        if failed:
            error = error or "; ".join(v.reason for v in failed)
            try:
                screenshot = engine.screenshot(
                    str(
                        Path(run_config["report_dir"])
                        / "screenshots"
                        / f"{test.id}.png"
                    )
                )
            except Exception:
                pass
        status = "PASS" if not failed else "FAIL"

    except Exception as exc:
        error = str(exc)
        console, api_errs = [], []
        try:
            console, api_errs = interceptor.snapshot()
        except Exception:
            pass
        try:
            screenshot = engine.screenshot(
                str(
                    Path(run_config["report_dir"])
                    / "screenshots"
                    / f"{test.id}.png"
                )
            )
        except Exception:
            pass
        status = "FAIL"
    finally:
        engine.stop()

    result = TestResult(
        id=test.id,
        name=test.name,
        status=status,
        duration=time.perf_counter() - started,
        response=response,
        error=error,
        screenshot=screenshot,
        validations=validations,
        console_errors=console,
        api_errors=api_errs,
        healed_selectors=list(engine.healed_selectors),
    )

    # Failure analysis — runs after engine is stopped (no browser needed)
    if result.status == "FAIL" and run_config.get("analyze_failures", True):
        try:
            analyzer = FailureAnalyzer(
                provider=run_config.get("ai_provider", "none"),
                model=run_config.get("ai_model", "gpt-4o-mini"),
            )
            result.failure_analysis = analyzer.analyze(result)
        except Exception:
            pass  # analysis is best-effort; never fail the run because of it

    return result
