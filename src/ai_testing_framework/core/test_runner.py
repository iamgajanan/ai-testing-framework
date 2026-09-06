from __future__ import annotations

__test__ = False

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..ai.failure_analyzer import FailureAnalyzer
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
from ..validators.file_validator import validate_file
from ..validators.regex_validator import validate_regex
from ..validators.table_validator import validate_table
from ..validators.ui_validator import validate_element_present, validate_text_contains, validate_url_contains
from .config import load_config


class TestRunner:
    def __init__(self, config: str | dict | None = None, base_url: str = "") -> None:
        self.config = load_config(config) if isinstance(config, str) or config is None else config
        self.base_url = base_url
        self._build_ai_validator()

    def _build_ai_validator(self) -> None:
        self.ai = AIValidator(self.config["ai"]["provider"], self.config["ai"]["model"])

    def set_ai_provider(self, provider: str) -> None:
        self.config["ai"]["provider"] = provider
        self._build_ai_validator()

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
        raise ValueError(f"Unsupported test suite format: {suffix}. Use .md, .json, .csv, .xlsx, or .xlsm")

    def run(self, test_file: str, browser: Optional[str] = None, test_id: Optional[str] = None,
            output_dir: Optional[str] = None, formats: Optional[list[str]] = None,
            workers: Optional[int] = None) -> list[TestResult]:
        suite = self.load_suite(test_file)
        selected = [t for t in suite.tests if not test_id or t.id == test_id]
        if not selected:
            raise ValueError(f"No matching test found for id={test_id!r}")
        report_dir = output_dir or self.config["report"]["output_dir"]
        suite_name = suite.name
        started_at = datetime.now(timezone.utc).isoformat()
        emit_formats = formats or self.config["report"].get("formats", ["html", "json"])
        n_workers = max(1, int(workers if workers is not None else self.config.get("parallel", {}).get("workers", 1)))
        run_config = {
            "browser_name": browser or self.config.get("browser", "chromium"),
            "headless": self.config.get("headless", True),
            "timeout": self.config.get("timeout", 30000),
            "ai_provider": self.config["ai"]["provider"],
            "ai_model": self.config["ai"]["model"],
            "base_url": self.base_url,
            "report_dir": report_dir,
            "analyze_failures": self.config.get("ai", {}).get("analyze_failures", True),
            "self_healing": self.config.get("self_healing", {}).get("enabled", True),
            "healing_confidence": self.config.get("self_healing", {}).get("min_confidence", 0.70),
        }
        results = run_parallel(selected, lambda test: _run_test_isolated(test, run_config), workers=n_workers)
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

    @staticmethod
    def _has_api_candidate(responses: list, validation) -> bool:
        url, method, status = validation.api_url or "", (validation.api_method or "").upper(), validation.api_status
        for item in responses:
            actual = str(item.get("url", ""))
            path = actual.split("?", 1)[0]
            url_match = not url or (url.startswith("/") and (path.endswith(url) or path.endswith(url.rstrip("/")))) or url in actual
            if url_match and (not method or str(item.get("method", "")).upper() == method) and (status is None or int(item.get("status", -1)) == int(status)):
                return True
        return False

    def _validate(self, page, validation, response: str, interceptor: Optional[NetworkInterceptor] = None) -> ValidationResult:
        return _validate(self.ai, page, validation, response, interceptor)


def _validate(ai: AIValidator, page, validation, response: str, interceptor: Optional[NetworkInterceptor] = None,
              artifact_dir: str = "reports", downloaded_files: Optional[list[str]] = None) -> ValidationResult:
    kind = validation.type.lower()
    if kind == "ai_semantic":
        result = ai.validate_response(response, str(validation.expected or ""), validation.prompt)
        passed, conf, reason = bool(result.get("pass")), float(result.get("confidence", 0)), result.get("reason", "")
        if passed and validation.min_confidence is not None and conf < validation.min_confidence:
            passed = False
            reason = f"AI said pass but confidence {conf:.0%} < required {validation.min_confidence:.0%}. " + reason
        return ValidationResult(kind, passed, reason, conf)
    if kind == "api_response":
        if interceptor is None:
            return ValidationResult(kind, False, "API interceptor is not available")
        passed, reason, actual = validate_api_response(
            interceptor.response_snapshot(), url=validation.api_url or "", method=validation.api_method or "",
            status=validation.api_status, request_headers=validation.api_request_headers,
            response_headers=validation.api_response_headers, request_body=validation.api_request_body,
            response_body=validation.api_response_body, json_schema=validation.api_json_schema,
            response_time_ms=validation.api_response_time_ms, json_path=validation.json_path or "",
            expected=validation.expected, body_contains=validation.body_contains or "")
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
        passed, reason = validate_text_contains(page, validation.selector or ".result-text, .result-container", str(validation.expected or ""), timeout=validation.timeout)
        return ValidationResult(kind, passed, reason)
    if kind == "url_contains":
        passed, reason = validate_url_contains(page, str(validation.expected or ""))
        return ValidationResult(kind, passed, reason)
    if kind == "table_validation":
        passed, reason = validate_table(page, validation.selector, validation.expected_columns, validation.row_condition)
        return ValidationResult(kind, passed, reason)
    if kind in {"file_validation", "download_validation", "upload_validation"}:
        path = validation.file_path
        if not path and downloaded_files:
            path = downloaded_files[-1]
        if not path:
            return ValidationResult(kind, False, "No file path supplied and no download was captured")
        passed, reason, meta = validate_file(
            path, base_dir=Path.cwd(), expected_filename=validation.expected_filename,
            expected_extension=validation.expected_extension, expected_mime=validation.expected_mime,
            min_size=validation.min_size, max_size=validation.max_size, text_contains=validation.file_text_contains,
            pattern=validation.file_pattern, file_type=validation.file_type, json_path=validation.json_path,
            expected=validation.expected, expected_columns=validation.expected_columns)
        return ValidationResult(kind, passed, reason, actual=meta)
    raise ValueError(f"Unsupported validation type: {validation.type!r}")


def _run_test_isolated(test: TestCase, run_config: dict) -> TestResult:
    started = time.perf_counter()
    validations: list[ValidationResult] = []
    error = response = ""
    screenshot = None
    console: list[str] = []
    api_errs: list[str] = []
    engine = PlaywrightEngine(browser_name=run_config["browser_name"], headless=run_config["headless"], timeout=run_config["timeout"],
                              ai_provider=run_config["ai_provider"], ai_model=run_config["ai_model"],
                              self_healing=run_config.get("self_healing", True), healing_confidence=run_config.get("healing_confidence", .70),
                              artifact_dir=run_config["report_dir"])
    engine.start()
    try:
        interceptor = NetworkInterceptor()
        assert engine.page is not None
        interceptor.attach(engine.page)
        engine.open(test.url, run_config["base_url"])
        for step in test.steps:
            engine.run_step(step)
        api_validations = [v for v in test.validations if v.type.lower() == "api_response"]
        if api_validations:
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                snapshot = interceptor.response_snapshot()
                if all(TestRunner._has_api_candidate(snapshot, v) for v in api_validations):
                    break
                engine.page.wait_for_timeout(50)
        response = engine.response_text()
        for validation in test.validations:
            validations.append(_validate(AIValidator(run_config["ai_provider"], run_config["ai_model"]), engine.page, validation, response, interceptor, run_config["report_dir"], engine.downloads))
        console, api_errs = interceptor.snapshot()
        if any(c.lower() == "console_errors" for c in test.error_checks) and console:
            validations.append(ValidationResult("console_errors", False, f"{len(console)} console error(s)"))
            error = "Console errors detected"
        if any(c.lower() == "api_errors" for c in test.error_checks) and api_errs:
            validations.append(ValidationResult("api_errors", False, f"{len(api_errs)} network error(s)"))
            error = error or "API/network errors detected"
        failed = [v for v in validations if not v.passed]
        if failed:
            error = error or "; ".join(v.reason for v in failed)
            try:
                screenshot = engine.screenshot(str(Path(run_config["report_dir"]) / "screenshots" / f"{test.id}.png"))
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
            screenshot = engine.screenshot(str(Path(run_config["report_dir"]) / "screenshots" / f"{test.id}.png"))
        except Exception:
            pass
        status = "FAIL"
    finally:
        engine.stop()
    result = TestResult(id=test.id, name=test.name, status=status, duration=time.perf_counter() - started,
                        response=response, error=error, screenshot=screenshot, validations=validations,
                        console_errors=console, api_errors=api_errs, healed_selectors=list(engine.healed_selectors))
    if result.status == "FAIL" and run_config.get("analyze_failures", True):
        try:
            result.failure_analysis = FailureAnalyzer(provider=run_config.get("ai_provider", "none"), model=run_config.get("ai_model", "gpt-4o-mini")).analyze(result)
        except Exception:
            pass
    return result
