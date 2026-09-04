from __future__ import annotations

from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from .element_locator import AIElementLocator


class PlaywrightEngine:
    """Thin synchronous Playwright adapter used by the test runner."""

    def __init__(
        self,
        browser_name: str = "chromium",
        headless: bool = True,
        timeout: int = 30000,
        ai_provider: str = "openai",
        ai_model: str = "gpt-4o-mini",
    ) -> None:
        self.browser_name = browser_name
        self.headless = headless
        self.timeout = timeout
        self.ai_locator = AIElementLocator(ai_provider, ai_model)
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.console_errors: list[str] = []
        self.api_errors: list[str] = []
        self.downloads: list[str] = []

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
        raise ValueError("Step requires either 'selector' or 'description'")

    def run_step(self, step: Any) -> Any:
        assert self.page is not None
        action = step.action.lower().strip()
        selector = step.selector
        description = getattr(step, "description", "")
        value = "" if step.value is None else str(step.value)
        timeout = getattr(step, "timeout", self.timeout)
        locator = None if action in {"wait_for_load_state"} else self._resolve_locator(selector, description)

        if action in {"type", "fill"}:
            locator.fill(value, timeout=timeout)
        elif action == "click":
            locator.click(timeout=timeout)
        elif action in {"check", "checkbox"}:
            locator.check(timeout=timeout)
        elif action == "uncheck":
            locator.uncheck(timeout=timeout)
        elif action in {"select", "select_option"}:
            locator.select_option(value, timeout=timeout)
        elif action == "hover":
            locator.hover(timeout=timeout)
        elif action in {"press", "keyboard"}:
            locator.press(value, timeout=timeout) if selector or description else self.page.keyboard.press(value)
        elif action in {"upload", "set_input_files"}:
            locator.set_input_files(value, timeout=timeout)
        elif action in {"wait", "wait_for_selector"}:
            locator.wait_for(state="visible", timeout=timeout)
        elif action in {"wait_for_response", "response"}:
            with self.page.expect_response(value, timeout=timeout) as response_info:
                if selector or description:
                    locator.click(timeout=timeout)
            return response_info.value
        elif action == "download":
            with self.page.expect_download(timeout=timeout) as download_info:
                if selector or description:
                    locator.click(timeout=timeout)
            download = download_info.value
            path = Path("reports") / "downloads" / download.suggested_filename
            path.parent.mkdir(parents=True, exist_ok=True)
            download.save_as(str(path))
            self.downloads.append(str(path))
            return str(path)
        elif action == "wait_for_load_state":
            self.page.wait_for_load_state(value or "networkidle", timeout=timeout)
        else:
            raise ValueError(f"Unsupported Playwright action: {step.action}")

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
