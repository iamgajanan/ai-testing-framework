from __future__ import annotations

import csv
from pathlib import Path

from ..core.models import Step, TestCase, TestSuite, Validation


class CSVParser:
    """Minimal CSV adapter retained as a Phase 1 compatibility extension."""

    def parse(self, path: str | Path) -> TestSuite:
        tests = {}
        with Path(path).open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                test_id = row["TestID"]
                test = tests.setdefault(test_id, TestCase(test_id, test_id, row.get("URL", "/")))
                action = row.get("Action", "").strip()
                if action:
                    test.steps.append(Step(action, row.get("Selector") or None, row.get("Value") or None, row.get("Expected", "")))
                validation = row.get("Validation", "").strip()
                if validation:
                    test.validations.append(Validation("ai_semantic", prompt=validation, expected=row.get("Expected", "")))
        return TestSuite("CSV Test Suite", list(tests.values()))
