from __future__ import annotations

from ai_testing_framework.automation.playwright_engine import PlaywrightEngine
from ai_testing_framework.core.models import Step


class FakeDialog:
    type = "alert"
    message = "hello"
    def __init__(self): self.action = None
    def accept(self): self.action = "accept"
    def dismiss(self): self.action = "dismiss"


class FakePage:
    def __init__(self):
        self.url = "http://127.0.0.1:8000/"
        self.default_timeout = None
        self.dialog = FakeDialog()
    def set_default_timeout(self, timeout): self.default_timeout = timeout
    def bring_to_front(self): pass
    def close(self): pass
    def evaluate(self, script, value=None):
        if value is not None:
            assert "localStorage.setItem" in script
            return None
        return None


class FakeContext:
    def __init__(self, pages): self._pages = pages
    @property
    def pages(self): return self._pages
    def add_cookies(self, cookies): self.cookies = cookies


def test_set_cookie_and_local_storage():
    engine = PlaywrightEngine()
    page = FakePage()
    engine.page = page
    engine.context = FakeContext([page])
    engine.run_step(Step(action="set_cookie", value={"name": "session", "value": "demo-session", "path": "/"}))
    assert engine.context.cookies[0]["name"] == "session"
    engine.run_step(Step(action="set_local_storage", value={"role": "user"}))


def test_dialog_configuration_accepts_and_dismisses():
    engine = PlaywrightEngine()
    page = FakePage()
    engine.page = page
    engine._dialog_action = "accept"
    engine._handle_dialog(page.dialog)
    assert page.dialog.action == "accept"
    page.dialog = FakeDialog()
    engine._dialog_action = "dismiss"
    engine._handle_dialog(page.dialog)
    assert page.dialog.action == "dismiss"


def test_switch_and_close_tab():
    engine = PlaywrightEngine()
    first, second = FakePage(), FakePage()
    first.url = "http://127.0.0.1:8000/"
    second.url = "http://127.0.0.1:8000/popup"
    engine.context = FakeContext([first, second])
    engine.page = first
    assert engine.run_step(Step(action="switch_tab", value="last")) is second
    assert engine.page is second
    assert engine.run_step(Step(action="switch_tab", value=0)) is first


def test_login_requires_complete_form_definition():
    engine = PlaywrightEngine()
    page = FakePage()
    engine.page = page
    try:
        engine.run_step(Step(action="login", value={"username": "demo"}))
    except ValueError as exc:
        assert "username_selector" in str(exc)
    else:
        raise AssertionError("Incomplete login definition should fail clearly")
