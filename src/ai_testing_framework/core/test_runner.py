from __future__ import annotations

# This module is framework code, not a pytest test module.
__test__ = False

import time
from pathlib import Path
from typing import Optional

from ..automation.network_interceptor import NetworkInterceptor
from ..automation.playwright_engine import PlaywrightEngine
from ..core.models import TestCase, TestResult, ValidationResult, TestSuite
from ..parsers.csv_parser import CSVParser
from ..parsers.json_parser import JSONParser
from ..parsers.md_parser import MarkdownParser
from ..parsers.xlsx_parser import XLSXParser
from ..reporters.html_reporter import write_html_report
from ..reporters.json_reporter import write_json_report
from ..validators.ai_validator import AIValidator
from ..validators.api_validator import validate_api_response
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

    def run(self, test_file: str, browser: Optional[str] = None, test_id: Optional[str] = None, output_dir: Optional[str] = None) -> list[TestResult]:
        suite = self.load_suite(test_file)
        selected = [t for t in suite.tests if not test_id or t.id == test_id]
        if not selected:
            raise ValueError(f"No matching test found for id={test_id}")
        browser_name = browser or self.config.get("browser", "chromium")
        results: list[TestResult] = []
        engine = PlaywrightEngine(
            browser_name,
            self.config.get("headless", True),
            self.config.get("timeout", 30000),
            self.config["ai"]["provider"],
            self.config["ai"]["model"],
        )
        engine.start()
        try:
            for test in selected:
                results.append(self._run_test(engine, test, output_dir or self.config["report"]["output_dir"]))
        finally:
            engine.stop()
        report_dir = output_dir or self.config["report"]["output_dir"]
        if self.config["report"].get("html", True):
            write_html_report(results, report_dir)
        if self.config["report"].get("json", True):
            write_json_report(results, report_dir)
        return results

    def _run_test(self, engine: PlaywrightEngine, test: TestCase, output_dir: str) -> TestResult:
        started = time.perf_counter()
        validations: list[ValidationResult] = []
        error = ""
        response = ""
        screenshot = None
        interceptor = NetworkInterceptor()
        engine.healed_selectors = []
        assert engine.page is not None
        interceptor.attach(engine.page)
        try:
            engine.open(test.url, self.base_url)
            for step in test.steps:
                engine.run_step(step)

            api_validations = [v for v in test.validations if v.type.lower() == "api_response"]
            if api_validations:
                deadline = time.monotonic() + 2.0
                while time.monotonic() < deadline:
                    snapshot = interceptor.response_snapshot()
                    if all(self._has_api_candidate(snapshot, v) for v in api_validations):
                        break
                    engine.page.wait_for_timeout(50)

            response = engine.response_text()
            for validation in test.validations:
                validations.append(self._validate(engine.page, validation, response, interceptor))
            console, api = interceptor.snapshot()
            if any(check.lower() == "console_errors" for check in test.error_checks) and console:
                validations.append(ValidationResult("console_errors", False, f"{len(console)} console error(s)"))
                error = "Console errors detected"
            if any(check.lower() == "api_errors" for check in test.error_checks) and api:
                validations.append(ValidationResult("api_errors", False, f"{len(api)} network error(s)"))
                error = error or "API/network errors detected"
            failed = [v for v in validations if not v.passed]
            if failed:
                error = error or "; ".join(v.reason for v in failed)
                screenshot = engine.screenshot(str(Path(output_dir) / "screenshots" / f"{test.id}.png"))
            status = "PASS" if not failed else "FAIL"
        except Exception as exc:
            error = str(exc)
            console, api = interceptor.snapshot()
            try:
                screenshot = engine.screenshot(str(Path(output_dir) / "screenshots" / f"{test.id}.png"))
            except Exception:
                screenshot = None
            status = "FAIL"
        else:
            console, api = interceptor.snapshot()
        return TestResult(
            test.id, test.name, status, time.perf_counter() - started,
            response, error, screenshot, validations, console, api,
            healed_selectors=list(engine.healed_selectors),
        )

    @staticmethod
    def _has_api_candidate(responses, validation) -> bool:
        url = validation.api_url or ""
        method = (validation.api_method or "").upper()
        status = validation.api_status
        for item in responses:
            actual_url = str(item.get("url", ""))
            url_match = (not url or (url.startswith("/") and (actual_url.split("?", 1)[0].endswith(url) or actual_url.split("?", 1)[0].endswith(url.rstrip("/")))) or (url in actual_url))
            method_match = not method or str(item.get("method", "")).upper() == method
            status_match = status is None or int(item.get("status", -1)) == int(status)
            if url_match and method_match and status_match:
                return True
        return False

    def _validate(self, page, validation, response: str, interceptor: NetworkInterceptor | None = None) -> ValidationResult:
        kind = validation.type.lower()
        if kind == "ai_semantic":
            result = self.ai.validate_response(response, str(validation.expected or ""), validation.prompt)
            return ValidationResult(kind, bool(result.get("pass")), result.get("reason", ""), float(result.get("confidence", 0)))
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
            selector = validation.selector or ".result-text, .result-container"
            if kind == "ui_text" and not validation.selector:
                passed = str(validation.expected or "").lower() in response.lower()
                return ValidationResult(kind, passed, f"Expected text: {validation.expected!r}")
            passed, reason = validate_text_contains(page, selector, str(validation.expected or ""), timeout=validation.timeout)
            return ValidationResult(kind, passed, reason)
        if kind == "url_contains":
            passed, reason = validate_url_contains(page, str(validation.expected or ""))
            return ValidationResult(kind, passed, reason)
        if kind == "table_validation":
            passed, reason = validate_table(page, validation.selector, validation.expected_columns, validation.row_condition)
            return ValidationResult(kind, passed, reason)
        raise ValueError(f"Unsupported validation type: {validation.type}")
