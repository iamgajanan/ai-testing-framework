from __future__ import annotations

from pathlib import Path
from typing import Any

from ..core.models import Step, TestCase, TestSuite, Validation


class XLSXParser:
    """Parse the first worksheet of an Excel test suite."""

    def parse(self, path: str | Path) -> TestSuite:
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise RuntimeError("XLSX support requires openpyxl. Install it with: pip install openpyxl") from exc

        workbook = load_workbook(Path(path), read_only=True, data_only=True)
        try:
            sheet = workbook.active
            rows = sheet.iter_rows(values_only=True)
            headers = [str(value).strip() if value is not None else "" for value in next(rows, ())]
            tests: dict[str, TestCase] = {}
            for values in rows:
                row = {headers[i]: values[i] if i < len(values) else None for i in range(len(headers)) if headers[i]}
                self._add_row(tests, row)
            return TestSuite("XLSX Test Suite", list(tests.values()))
        finally:
            workbook.close()

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
                    timeout=int(float(self._value(row, "Timeout", default="30000"))),
                )
            )
        expected = self._value(row, "Expected")
        validation = self._value(row, "Validation", "Prompt")
        validation_type = self._value(row, "ValidationType")
        if validation or validation_type:
            test.validations.append(
                Validation(
                    type=validation_type or "ai_semantic",
                    prompt=validation,
                    expected=expected,
                    selector=self._value(row, "ValidationSelector") or None,
                    pattern=self._value(row, "Pattern") or None,
                    row_condition=self._value(row, "RowCondition") or None,
                    expected_columns=[c.strip() for c in self._value(row, "ExpectedColumns").split("|") if c.strip()],
                )
            )
        error_checks = self._value(row, "ErrorChecks")
        for check in error_checks.split("|"):
            check = check.strip()
            if check and check not in test.error_checks:
                test.error_checks.append(check)
        if expected and not test.expected:
            test.expected = expected
