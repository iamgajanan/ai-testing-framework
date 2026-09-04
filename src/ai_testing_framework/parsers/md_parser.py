from __future__ import annotations

import re
from pathlib import Path

from ..core.models import Step, TestCase, TestSuite, Validation


class MarkdownParser:
    _step_re = re.compile(r"^\s*\d+\.\s+(.*)$")
    # Test IDs may contain hyphens, e.g. "TC-001".
    _test_re = re.compile(r"^##\s+Test:\s*([A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)\s*-\s*(.+)$", re.I)

    def parse(self, path: str | Path) -> TestSuite:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
        suite_name = "AI Test Suite"
        current = None
        tests = []

        for raw in lines:
            line = raw.strip()
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
                current.validations.append(Validation(type="ui_text", expected=line.split(":", 1)[1].strip()))
            else:
                step_match = self._step_re.match(line)
                if step_match:
                    self._parse_step(step_match.group(1), current)

        if current:
            tests.append(current)
        if not tests:
            raise ValueError("Markdown suite contains no test cases.")
        return TestSuite(name=suite_name, tests=tests)

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
        else:
            test.steps.append(Step("raw", selector, text, text, timeout))
