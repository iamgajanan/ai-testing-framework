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
        return TestSuite("CSV Test Suite", list(tests.values()))

    @staticmethod
    def _value(row: dict[str, Any], *names: str, default: str = "") -> str:
        for name in names:
            value = row.get(name)
            if value is not None and str(value).strip():
                return str(value).strip()
        return default

    def _add_row(self, tests: dict[str, TestCase], row: dict[str, Any]) -> None:
        test_id = self._value(row, "TestID", "test_id")
        if not test_id:
            return
        test = tests.setdefault(
            test_id,
            TestCase(
                test_id,
                self._value(row, "Name", "TestName", default=test_id),
                self._value(row, "URL", "Url", default="/"),
            ),
        )
        action = self._value(row, "Action")
        if action:
            test.steps.append(
                Step(
                    action=action,
                    selector=self._value(row, "Selector") or None,
                    value=self._value(row, "Value") or None,
                    description=self._value(row, "Description"),
                    timeout=int(self._value(row, "Timeout", default="30000")),
                )
            )
        expected = self._value(row, "Expected")
        validation = self._value(row, "Validation", "Prompt")
        if validation or self._value(row, "ValidationType"):
            validation_type = self._value(row, "ValidationType", default="ai_semantic")
            test.validations.append(
                Validation(
                    type=validation_type,
                    prompt=validation,
                    expected=expected,
                    selector=self._value(row, "ValidationSelector") or None,
                    pattern=self._value(row, "Pattern") or None,
                    row_condition=self._value(row, "RowCondition") or None,
                    expected_columns=[c.strip() for c in self._value(row, "ExpectedColumns").split("|") if c.strip()],
                )
            )
        error_checks = self._value(row, "ErrorChecks")
        if error_checks:
            for check in error_checks.split("|"):
                check = check.strip()
                if check and check not in test.error_checks:
                    test.error_checks.append(check)
        if expected and not test.expected:
            test.expected = expected
