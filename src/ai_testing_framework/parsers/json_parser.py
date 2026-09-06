from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from ..core.models import Step, TestCase, TestSuite, Validation


class JSONParser:
    def parse(self, path: str | Path) -> TestSuite:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        tests = [self._test(item) for item in data.get("tests", [])]
        if not tests:
            raise ValueError("JSON suite must contain at least one test in 'tests'.")
        return TestSuite(name=data.get("test_suite", "AI Test Suite"), tests=tests)

    def _test(self, item: Dict[str, Any]) -> TestCase:
        return TestCase(
            id=str(item["id"]),
            name=item.get("name", str(item["id"])),
            url=item.get("url", "/"),
            steps=[Step(**self._step(s)) for s in item.get("steps", [])],
            validations=[Validation(**self._validation(v)) for v in item.get("validations", [])],
            error_checks=item.get("error_checks", []),
            expected=item.get("expected", ""),
        )

    @staticmethod
    def _step(step: Dict[str, Any]) -> Dict[str, Any]:
        allowed = {"action", "selector", "value", "description", "timeout"}
        return {k: v for k, v in step.items() if k in allowed}

    @staticmethod
    def _validation(validation: Dict[str, Any]) -> Dict[str, Any]:
        allowed = {
            "type", "prompt", "expected", "selector", "pattern", "expected_columns",
            "row_condition", "api_url", "api_method", "api_status",
            "api_request_headers", "api_response_headers", "api_request_body",
            "api_response_body", "api_json_schema", "api_response_time_ms",
            "json_path", "body_contains", "file_path", "expected_filename",
            "expected_extension", "expected_mime", "min_size", "max_size",
            "file_type", "file_text_contains", "file_pattern", "timeout", "min_confidence",
        }
        return {k: v for k, v in validation.items() if k in allowed}
