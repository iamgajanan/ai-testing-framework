from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from ..core.models import Step, TestCase, TestSuite, Validation


class MarkdownParser:
    """Parse human-readable Markdown test suites plus structured YAML validation blocks."""

    _step_re = re.compile(r"^\s*\d+\.\s+(.*)$")
    _test_re = re.compile(r"^##\s+Test:\s*([A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)\s*-\s*(.+)$", re.I)
    _known_validation_fields = set(Validation.__dataclass_fields__)

    def parse(self, path: str | Path) -> TestSuite:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
        suite_name = "AI Test Suite"
        current: TestCase | None = None
        tests: list[TestCase] = []
        yaml_lines: list[str] = []
        in_yaml = False
        yaml_kind = "validations"

        def flush_yaml() -> None:
            nonlocal yaml_lines
            if not yaml_lines or current is None:
                yaml_lines = []
                return
            try:
                data = yaml.safe_load("\n".join(yaml_lines))
            except yaml.YAMLError as exc:
                raise ValueError(f"Invalid Markdown YAML {yaml_kind} block: {exc}") from exc
            if data is not None:
                self._apply_structured_block(current, data, yaml_kind)
            yaml_lines = []

        for raw in lines:
            line = raw.strip()
            if in_yaml:
                if line.startswith("```"):
                    flush_yaml()
                    in_yaml = False
                else:
                    yaml_lines.append(raw)
                continue

            if line.lower().startswith("```yaml") or line.lower().startswith("```yml"):
                if current is not None:
                    in_yaml = True
                    yaml_kind = "validations"
                continue

            if line.startswith("# Test Suite:"):
                suite_name = line.split(":", 1)[1].strip()
                continue
            match = self._test_re.match(line)
            if match:
                if current:
                    tests.append(current)
                current = TestCase(id=match.group(1), name=match.group(2).strip(), url="/")
                continue
            if current is None:
                continue

            if line.lower().startswith("- url:"):
                current.url = line.split(":", 1)[1].strip()
            elif line.lower().startswith("- expected:"):
                current.expected = line.split(":", 1)[1].strip()
                current.validations.append(Validation(type="ai_semantic", prompt="Validate the expected outcome", expected=current.expected))
            elif line.lower().startswith("- ai validation:"):
                prompt = line.split(":", 1)[1].strip().strip('"')
                current.validations.append(Validation(type="ai_semantic", prompt=prompt))
            elif line.lower().startswith("- fallback check:"):
                text = line.split(":", 1)[1].strip()
                prefix = "Response should match regex:"
                pattern = text.split(prefix, 1)[1].strip() if prefix.lower() in text.lower() else text
                current.validations.append(Validation(type="regex", pattern=pattern))
            elif line.lower().startswith("- ui check:"):
                current.validations.append(Validation(type="ui_text", expected=line.split(":", 1)[1].strip()))
            elif line.lower().startswith("- validation:"):
                raw_validation = line.split(":", 1)[1].strip()
                if raw_validation.startswith("{"):
                    self._apply_structured_block(current, json.loads(raw_validation), "validations")
                else:
                    current.validations.append(Validation(type="ui_text", expected=raw_validation))
            else:
                step_match = self._step_re.match(line)
                if step_match:
                    self._parse_step(step_match.group(1), current)

        if in_yaml:
            flush_yaml()
        if current:
            tests.append(current)
        if not tests:
            raise ValueError("Markdown suite contains no test cases.")
        return TestSuite(name=suite_name, tests=tests)

    def _apply_structured_block(self, test: TestCase, data: Any, kind: str) -> None:
        if isinstance(data, dict):
            items = data.get("validations") if kind == "validations" and "validations" in data else data
            if isinstance(items, dict):
                items = [items]
        elif isinstance(data, list):
            items = data
        else:
            raise ValueError(f"Markdown {kind} block must contain a mapping or list")

        if kind == "validations":
            for item in items:
                if not isinstance(item, dict) or "type" not in item:
                    raise ValueError("Each Markdown validation must be a mapping with a 'type'")
                normalized = {k: v for k, v in item.items() if k in self._known_validation_fields}
                test.validations.append(Validation(**normalized))

    def _parse_step(self, text: str, test: TestCase) -> None:
        lowered = text.lower()
        selector_match = re.search(r"\(\s*selector:\s*([^\)]+)\)", text, re.I)
        selector = selector_match.group(1).strip() if selector_match else None
        timeout_match = re.search(r"max wait:\s*(\d+)s", text, re.I)
        timeout = int(timeout_match.group(1)) * 1000 if timeout_match else 30000

        if lowered.startswith("upload file:"):
            value = text.split(":", 1)[1].split("(", 1)[0].strip()
            test.steps.append(Step("upload", selector, value, text, timeout))
        elif lowered.startswith("enter query:") or lowered.startswith("type "):
            value = text.split(":", 1)[1].split("(", 1)[0].strip().strip('"')
            test.steps.append(Step("type", selector, value, text, timeout))
        elif lowered.startswith("click"):
            test.steps.append(Step("click", selector, None, text, timeout))
        elif lowered.startswith("wait"):
            test.steps.append(Step("wait", selector, None, text, timeout))
        elif lowered.startswith("evaluate:"):
            value = text.split(":", 1)[1].strip()
            test.steps.append(Step("evaluate", None, value, text, timeout))
        else:
            test.steps.append(Step("raw", selector, text, text, timeout))
