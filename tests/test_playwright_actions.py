from types import SimpleNamespace
from unittest.mock import Mock

from ai_testing_framework.automation.playwright_engine import PlaywrightEngine


def test_run_step_supports_richer_actions():
    engine = PlaywrightEngine()
    page = Mock()
    engine.page = page

    for action, selector, value in [
        ("fill", "#name", "Gajanan"),
        ("check", "#terms", None),
        ("uncheck", "#terms", None),
        ("select", "#country", "IN"),
        ("hover", "#menu", None),
        ("press", "#query", "Enter"),
        ("wait", "#result", None),
    ]:
        engine.run_step(SimpleNamespace(action=action, selector=selector, value=value, timeout=1000))

    page.locator.assert_any_call("#name")
    page.locator.assert_any_call("#terms")
    page.locator.assert_any_call("#country")
    page.locator.assert_any_call("#menu")
    page.locator.assert_any_call("#query")
    page.locator.assert_any_call("#result")


def test_press_without_selector_uses_keyboard():
    engine = PlaywrightEngine()
    page = Mock()
    engine.page = page

    engine.run_step(SimpleNamespace(action="press", selector=None, value="Escape", timeout=1000))

    page.keyboard.press.assert_called_once_with("Escape")


def test_upload_action_sets_files(tmp_path):
    engine = PlaywrightEngine()
    page = Mock()
    engine.page = page

    upload_file = tmp_path / "a.txt"
    upload_file.write_text("test upload")

    engine.run_step(
        SimpleNamespace(
            action="upload",
            selector="#file",
            value=str(upload_file),
            timeout=1000,
        )
    )

    page.locator.return_value.set_input_files.assert_called_once_with(
        str(upload_file), timeout=1000
    )
