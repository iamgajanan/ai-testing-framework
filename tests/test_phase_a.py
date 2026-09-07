from __future__ import annotations

import json

from ai_testing_framework.automation.playwright_engine import PlaywrightEngine
from ai_testing_framework.ai.test_generator import TestGenerator
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

    @property
    def first(self):
        return self

    def count(self):
        return 1

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


def test_heuristic_generator_does_not_submit_password_forms():
    page_info = {
        "title": "Login Demo",
        "inputs": [
            {"tag": "input", "id": "username", "type": "text"},
            {"tag": "input", "id": "password", "type": "password"},
        ],
        "buttons": [{"tag": "button", "id": "login", "text": "Login", "type": "submit"}],
        "headings": ["Login Demo"],
        "links": [],
        "tables": [],
    }
    suite = TestGenerator(provider="none")._heuristic_generate(page_info, "/auth")
    assert [test["name"] for test in suite["tests"]] == ["Page loads with expected elements"]
    assert all(step["action"] != "click" for test in suite["tests"] for step in test["steps"])


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


# ---------------------------------------------------------------------------
# New actions: scroll, drag, focus, clear, iframe
# ---------------------------------------------------------------------------

class FakePageActions:
    """Minimal mock for scroll/drag/focus/clear/frame actions."""
    def __init__(self):
        self.evaluated = []
        self.dragged = []
        self.frame_sel = None
        self.url = "http://example.com/"
        self.default_timeout = 30000

    def set_default_timeout(self, t): self.default_timeout = t
    def evaluate(self, script, *args): self.evaluated.append(script); return None
    def drag_and_drop(self, src, tgt, timeout=30000): self.dragged.append((src, tgt))
    def frame_locator(self, sel): self.frame_sel = sel; return f"frame:{sel}"

    def locator(self, sel):
        class L:
            def __init__(self):
                self.focused = False; self.cleared = False
                self.count = lambda: 1
            @property
            def first(self): return self
            def scroll_into_view_if_needed(self, timeout=30000): pass
            def focus(self, timeout=30000): self.focused = True
            def clear(self, timeout=30000): self.cleared = True
            def is_visible(self): return True
            def is_enabled(self): return True
            def is_checked(self): return False
            def is_editable(self): return True
        return L()


def _engine_with(page):
    engine = PlaywrightEngine(self_healing=False)
    engine.page = page
    return engine


def test_scroll_page_to_bottom():
    page = FakePageActions()
    engine = _engine_with(page)
    engine.run_step(Step(action="scroll"))
    assert any("scrollTo" in e for e in page.evaluated)


def test_scroll_to_xy_coordinates():
    page = FakePageActions()
    engine = _engine_with(page)
    import json
    engine.run_step(Step(action="scroll", value=json.dumps({"x": 0, "y": 500})))
    assert any("scrollTo(0,500)" in e for e in page.evaluated)


def test_drag_and_drop():
    page = FakePageActions()
    engine = _engine_with(page)
    engine.run_step(Step(action="drag", selector="#source", value="#target"))
    assert ("#source", "#target") in page.dragged


def test_drag_requires_selector_and_value():
    import pytest
    page = FakePageActions()
    engine = _engine_with(page)
    with pytest.raises(ValueError, match="drag requires"):
        engine.run_step(Step(action="drag", selector="#source"))


def test_focus_action():
    page = FakePageActions()
    engine = _engine_with(page)
    engine.run_step(Step(action="focus", selector="#input"))
    # no exception = success (mock locator.focus() is a no-op)


def test_clear_action():
    page = FakePageActions()
    engine = _engine_with(page)
    engine.run_step(Step(action="clear", selector="#input"))
    # no exception = success


def test_iframe_action_returns_frame_locator():
    page = FakePageActions()
    engine = _engine_with(page)
    result = engine.run_step(Step(action="frame", value="iframe#payment"))
    assert result == "frame:iframe#payment"
    assert page.frame_sel == "iframe#payment"


def test_iframe_requires_value():
    import pytest
    page = FakePageActions()
    engine = _engine_with(page)
    with pytest.raises(ValueError, match="frame action requires"):
        engine.run_step(Step(action="frame"))
