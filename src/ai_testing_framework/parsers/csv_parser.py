from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ..core.models import Step, TestCase, TestSuite, Validation


class CSVParser:
    """Parse a row-oriented, data-driven test suite from CSV."""

    def parse(self, path: str | Path) -> TestSuite:
        tests: dict[str, TestCase] = {}
        with Path(path).open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                self._add_row(tests, row)
        if not tests:
            raise ValueError("CSV suite must contain at least one row with TestID.")
        return TestSuite("CSV Test Suite", list(tests.values()))

    @staticmethod
    def _value(row: dict[str, Any], *names: str, default: str = "") -> str:
        for name in names:
            value = row.get(name)
            if value is not None and str(value).strip():
                return str(value).strip()
        return default

    @staticmethod
    def _json(value: str) -> Any:
        if not value:
            return None
        try:
            return __import__("json").loads(value)
        except (ValueError, TypeError):
            return value

    @staticmethod
    def _headers(value: str) -> dict[str, str]:
        result = {}
        for item in value.split("|") if value else []:
            if ":" in item:
                key, val = item.split(":", 1)
                result[key.strip()] = val.strip()
        return result

    def _add_row(self, tests: dict[str, TestCase], row: dict[str, Any]) -> None:
        test_id = self._value(row, "TestID", "test_id")
        if not test_id:
            return
        test = tests.setdefault(test_id, TestCase(test_id, self._value(row, "Name", "TestName", default=test_id), self._value(row, "URL", "Url", default="/")))
        action = self._value(row, "Action")
        if action:
            test.steps.append(Step(action, self._value(row, "Selector") or None, self._value(row, "Value") or None, self._value(row, "Description"), int(float(self._value(row, "Timeout", default="30000")))))
        expected = self._value(row, "Expected")
        validation_type = self._value(row, "ValidationType")
        validation = self._value(row, "Validation", "Prompt")
        api_url = self._value(row, "APIUrl", "ApiUrl")
        file_path = self._value(row, "FilePath", "Path")
        if validation or validation_type or api_url or file_path:
            api_status = self._value(row, "APIStatus", "ApiStatus")
            threshold = self._value(row, "APIResponseTimeMs", "ResponseTimeMs")
            min_size = self._value(row, "MinSize")
            max_size = self._value(row, "MaxSize")
            confidence = self._value(row, "MinConfidence")
            test.validations.append(Validation(
                type=validation_type or ("file_validation" if file_path else "ai_semantic"),
                prompt=validation, expected=self._json(expected),
                selector=self._value(row, "ValidationSelector") or None,
                pattern=self._value(row, "Pattern") or None,
                row_condition=self._value(row, "RowCondition") or None,
                expected_columns=[c.strip() for c in self._value(row, "ExpectedColumns").split("|") if c.strip()],
                api_url=api_url or None,
                api_method=self._value(row, "APIMethod", "ApiMethod") or None,
                api_status=int(float(api_status)) if api_status else None,
                api_request_headers=self._headers(self._value(row, "APIRequestHeaders", "RequestHeaders")),
                api_response_headers=self._headers(self._value(row, "APIResponseHeaders", "ResponseHeaders")),
                api_request_body=self._json(self._value(row, "APIRequestBody", "RequestBody")),
                api_response_body=self._json(self._value(row, "APIResponseBody", "ResponseBody")),
                api_json_schema=self._json(self._value(row, "APIJsonSchema", "JSONSchema")),
                api_response_time_ms=float(threshold) if threshold else None,
                json_path=self._value(row, "JSONPath", "JsonPath") or None,
                body_contains=self._value(row, "BodyContains") or None,
                file_path=file_path or None,
                expected_filename=self._value(row, "ExpectedFilename") or None,
                expected_extension=self._value(row, "ExpectedExtension") or None,
                expected_mime=self._value(row, "ExpectedMIME", "ExpectedMime") or None,
                min_size=int(float(min_size)) if min_size else None,
                max_size=int(float(max_size)) if max_size else None,
                file_type=self._value(row, "FileType") or None,
                file_text_contains=self._value(row, "FileTextContains") or None,
                file_pattern=self._value(row, "FilePattern") or None,
                timeout=int(float(self._value(row, "Timeout", default="5000"))),
                min_confidence=float(confidence) if confidence else None,
            ))
        for check in self._value(row, "ErrorChecks").split("|"):
            check = check.strip()
            if check and check not in test.error_checks:
                test.error_checks.append(check)
        if expected and not test.expected:
            test.expected = expected
