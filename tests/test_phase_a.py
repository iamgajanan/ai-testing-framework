from __future__ import annotations

import json

from ai_testing_framework.automation.playwright_engine import PlaywrightEngine
from ai_testing_framework.core.models import Step, StepResult, TestResult
from ai_testing_framework.parsers.md_parser import MarkdownParser
from ai_testing_framework.reporters.history import append_history
from ai_testing_framework.reporters.html_reporter import write_html_report
from ai_testing_framework.validators.ui_validator import (
    validate_element_attribute,
    validate_element_count,
    validate_element_state,
    validate_element_value,
)


class FakeLocator:
    def __init__(self, *, attribute=None, value="", visible=True, enabled=True, checked=False):
        self.attribute = attribute
        self.value = value
        self.visible = visible
        self.enabled = enabled
        self.checked = checked

    def get_attribute(self, name):
        return self.attribute if name == "aria-label" else None

    def input_value(self):
        return self.value

    def is_visible(self):
        return self.visible

    def is_enabled(self):
        return self.enabled

    def is_checked(self):
        return self.checked

    def is_editable(self):
        return self.enabled


class FakePage:
    def __init__(self):
        self.locator_obj = FakeLocator(attribute="Search", value="hello")

    def locator(self, selector):
        return self.locator_obj


def test_evaluate_action_uses_page_evaluate():
    engine = PlaywrightEngine()

    class Page:
        def evaluate(self, script):
            assert script == "document.body.dataset.test = 'ok'; 7"
            return 7

    engine.page = Page()
    assert engine.run_step(Step(action="evaluate", value="document.body.dataset.test = 'ok'; 7")) == 7


def test_ui_state_and_attribute_validators():
    page = FakePage()
    assert validate_element_attribute(page, "#search", "aria-label", "Search")[0]
    assert validate_element_value(page, "#search", "hello")[0]
    assert validate_element_state(page, "#search", "visible", True)[0]
    assert validate_element_state(page, "#search", "enabled", True)[0]
    assert validate_element_count(page, "#search", 1)[0]


def test_markdown_structured_validation_block(tmp_path):
    path = tmp_path / "suite.md"
    path.write_text(
        """# Test Suite: Phase A\n\n## Test: TC-001 - Structured validations\n- URL: /\n- Steps:\n  1. Evaluate: document.title\n- Validations:\n```yaml\nvalidations:\n  - type: element_present\n    selector: '#query'\n  - type: element_attribute\n    selector: '#submit'\n    attribute: 'type'\n    expected: 'submit'\n  - type: element_value\n    selector: '#query'\n    expected: 'OpenAI'\n  - type: element_count\n    selector: 'button'\n    expected: 1\n  - type: element_enabled\n    selector: '#submit'\n```\n""",
        encoding="utf-8",
    )
    suite = MarkdownParser().parse(path)
    assert len(suite.tests) == 1
    assert [v.type for v in suite.tests[0].validations] == [
        "element_present", "element_attribute", "element_value", "element_count", "element_enabled"
    ]
    assert suite.tests[0].steps[0].action == "evaluate"


def test_html_report_contains_step_trace_and_flaky_section(tmp_path):
    result_pass = TestResult(
        id="TC-001", name="Trace test", status="PASS", duration=0.1,
        steps=[StepResult(action="click", selector="#submit", status="PASS", duration=0.01)],
    )
    result_fail = TestResult(id="TC-001", name="Trace test", status="FAIL", duration=0.2)
    append_history([result_pass], str(tmp_path), suite_name="Phase A")
    append_history([result_fail], str(tmp_path), suite_name="Phase A")
    append_history([result_pass], str(tmp_path), suite_name="Phase A")
    report = write_html_report([result_pass], str(tmp_path), suite_name="Phase A")
    html = (tmp_path / "test_report.html").read_text(encoding="utf-8")
    assert report.endswith("test_report.html")
    assert "Step execution trace" in html
    assert "click" in html
    assert "Flaky tests" in html
    assert "TC-001" in html

    history = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
    assert len(history) == 3
