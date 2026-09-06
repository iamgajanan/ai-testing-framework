from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from .element_locator import AIElementLocator
from .self_healing import SelfHealing


class PlaywrightEngine:
    """Thin synchronous Playwright adapter used by the test runner."""

    def __init__(self, browser_name: str = "chromium", headless: bool = True, timeout: int = 30000,
                 ai_provider: str = "none", ai_model: str = "gpt-4o-mini", self_healing: bool = True,
                 healing_confidence: float = 0.70, artifact_dir: str = "reports") -> None:
        self.browser_name = browser_name
        self.headless = headless
        self.timeout = timeout
        self.artifact_dir = Path(artifact_dir)
        self.ai_locator = AIElementLocator(ai_provider, ai_model)
        self.self_healing = SelfHealing(ai_provider, ai_model, healing_confidence) if self_healing else None
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.console_errors: list[str] = []
        self.api_errors: list[str] = []
        self.downloads: list[str] = []
        self.uploads: list[str] = []
        self.healed_selectors: list[dict[str, Any]] = []
        self.dialogs: list[dict[str, Any]] = []

    def start(self) -> None:
        self.playwright = sync_playwright().start()
        browser_type = getattr(self.playwright, self.browser_name)
        self.browser = browser_type.launch(headless=self.headless)
        self.context = self.browser.new_context(accept_downloads=True)
        self.page = self.context.new_page()
        self.page.set_default_timeout(self.timeout)
        self._attach_listeners()

    def stop(self) -> None:
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None

    def _attach_listeners(self) -> None:
        assert self.page is not None
        self.page.on("console", lambda msg: self.console_errors.append(msg.text) if msg.type == "error" else None)
        self.page.on("requestfailed", lambda request: self.api_errors.append(f"{request.method} {request.url}: {request.failure}"))
        self.page.on("dialog", self._handle_dialog)

    def _handle_dialog(self, dialog) -> None:
        # Default is dismiss so an unexpected dialog never deadlocks a test.
        action = getattr(self, "_dialog_action", "dismiss")
        self.dialogs.append({"type": dialog.type, "message": dialog.message, "action": action})
        if action == "accept":
            dialog.accept()
        else:
            dialog.dismiss()

    def open(self, url: str, base_url: str = "") -> None:
        assert self.page is not None
        target = f"{base_url.rstrip('/')}/{url.lstrip('/')}" if base_url and url.startswith("/") else url
        self.page.goto(target, wait_until="domcontentloaded")

    def _resolve_locator(self, selector: str | None, description: str = ""):
        assert self.page is not None
        if selector:
            return self.page.locator(selector)
        if description:
            return self.ai_locator.find_element(self.page, description)
        raise ValueError("Step requires either 'selector' or 'description'.")

    def _try_heal(self, selector: str, description: str, action_fn, timeout: int):
        locator = self.page.locator(selector)
        try:
            return action_fn(locator)
        except Exception as original:
            if not self.self_healing:
                raise
            healed_selector = self.self_healing.heal_selector(self.page, selector, description)
            if healed_selector:
                self.healed_selectors.append({
                    "failed_selector": selector,
                    "healed_selector": healed_selector,
                    "reason": self.self_healing.last_reason,
                    "confidence": self.self_healing.last_confidence,
                })
                return action_fn(self.page.locator(healed_selector))
            raise original

    def _set_cookie(self, cookie: dict[str, Any]) -> None:
        assert self.context is not None and self.page is not None
        item = dict(cookie)
        if "url" not in item and "domain" not in item:
            item["url"] = self.page.url
        if "domain" in item and "path" not in item:
            item["path"] = "/"
        self.context.add_cookies([item])

    def _set_local_storage(self, values: dict[str, Any]) -> None:
        assert self.page is not None
        self.page.evaluate("""(items) => { for (const [k,v] of Object.entries(items)) localStorage.setItem(k, String(v)); }""", values)

    def _login(self, value: Any) -> None:
        if not isinstance(value, dict):
            raise ValueError("Login step value must be an object")
        username_selector = value.get("username_selector")
        password_selector = value.get("password_selector")
        submit_selector = value.get("submit_selector")
        if not username_selector or not password_selector or not submit_selector:
            raise ValueError("Login requires username_selector, password_selector and submit_selector")
        self.page.locator(username_selector).fill(str(value.get("username", "")))
        self.page.locator(password_selector).fill(str(value.get("password", "")))
        self.page.locator(submit_selector).click()
        if value.get("wait_for_load_state"):
            self.page.wait_for_load_state(str(value["wait_for_load_state"]))

    def _switch_tab(self, value: Any) -> Page:
        assert self.context is not None
        pages = self.context.pages
        if not pages:
            raise ValueError("No browser pages are open")
        if value is None or value == "last":
            target = pages[-1]
        elif isinstance(value, int) or str(value).isdigit():
            index = int(value)
            if index < 0 or index >= len(pages):
                raise IndexError(f"Tab index out of range: {index}")
            target = pages[index]
        else:
            target = next((p for p in pages if str(value) in p.url), None)
            if target is None:
                raise ValueError(f"No tab URL matched {value!r}")
        target.bring_to_front()
        self.page = target
        self.page.set_default_timeout(self.timeout)
        return target

    def run_step(self, step: Any) -> Any:
        assert self.page is not None
        action = step.action.lower().strip()
        selector: Optional[str] = step.selector
        description: str = getattr(step, "description", "") or ""
        value = step.value
        value_text = "" if value is None else str(value)
        timeout: int = getattr(step, "timeout", self.timeout)

        if action in {"evaluate", "javascript", "js"}:
            if not value_text.strip():
                raise ValueError("Evaluate step requires JavaScript in 'value'.")
            return self.page.evaluate(value_text)
        if action in {"set_cookie", "cookie"}:
            cookies = value if isinstance(value, list) else [value]
            if not all(isinstance(c, dict) for c in cookies):
                raise ValueError("set_cookie value must be a cookie object or list of cookie objects")
            for cookie in cookies:
                self._set_cookie(cookie)
            return
        if action in {"set_local_storage", "local_storage"}:
            if not isinstance(value, dict):
                raise ValueError("set_local_storage value must be an object")
            self._set_local_storage(value)
            return
        if action in {"login", "login_form"}:
            return self._login(value)
        if action in {"accept_dialog", "accept_alert"}:
            self._dialog_action = "accept"
            return
        if action in {"dismiss_dialog", "dismiss_alert"}:
            self._dialog_action = "dismiss"
            return
        if action in {"switch_tab", "switch_page"}:
            return self._switch_tab(value)
        if action in {"close_tab", "close_page"}:
            if len(self.context.pages) <= 1:
                raise ValueError("Cannot close the only browser tab")
            self.page.close()
            return self._switch_tab("last")
        if action in {"press", "keyboard"} and not selector and not description:
            self.page.keyboard.press(value_text)
            return
        if action == "wait_for_load_state":
            self.page.wait_for_load_state(value_text or "networkidle", timeout=timeout)
            return

        if action in {"upload", "set_input_files"}:
            upload_path = Path(value_text).expanduser()
            if not upload_path.exists() or not upload_path.is_file():
                raise FileNotFoundError(f"Upload file does not exist: {upload_path}")
            self.uploads.append(str(upload_path.resolve()))

        locator = self._resolve_locator(selector, description)
        heal = lambda fn: self._try_heal(selector, description, fn, timeout) if selector and self.self_healing else fn(locator)

        if action in {"type", "fill"}:
            heal(lambda l: l.fill(value_text, timeout=timeout))
        elif action == "click":
            heal(lambda l: l.click(timeout=timeout))
        elif action in {"check", "checkbox"}:
            heal(lambda l: l.check(timeout=timeout))
        elif action == "uncheck":
            heal(lambda l: l.uncheck(timeout=timeout))
        elif action in {"select", "select_option"}:
            heal(lambda l: l.select_option(value_text, timeout=timeout))
        elif action == "hover":
            heal(lambda l: l.hover(timeout=timeout))
        elif action in {"press", "keyboard"}:
            heal(lambda l: l.press(value_text, timeout=timeout))
        elif action in {"upload", "set_input_files"}:
            heal(lambda l: l.set_input_files(value_text, timeout=timeout))
        elif action in {"wait", "wait_for_selector"}:
            heal(lambda l: l.wait_for(state="visible", timeout=timeout))
        elif action in {"wait_for_response", "response"}:
            with self.page.expect_response(value_text, timeout=timeout) as response_info:
                if selector or description:
                    locator.click(timeout=timeout)
            return response_info.value
        elif action == "download":
            with self.page.expect_download(timeout=timeout) as download_info:
                if selector or description:
                    locator.click(timeout=timeout)
            download = download_info.value
            target = self.artifact_dir / "downloads" / download.suggested_filename
            target.parent.mkdir(parents=True, exist_ok=True)
            download.save_as(str(target))
            self.downloads.append(str(target))
            return str(target)
        else:
            raise ValueError(f"Unsupported Playwright action: {step.action!r}")

    def response_text(self) -> str:
        assert self.page is not None
        return self.page.locator("body").inner_text()

    def screenshot(self, path: str) -> str:
        assert self.page is not None
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(target), full_page=True)
        return str(target)

    def errors(self) -> tuple[list[str], list[str]]:
        return self.console_errors, self.api_errors
