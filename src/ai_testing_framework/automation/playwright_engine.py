from __future__ import annotations

from pathlib import Path
from typing import Tuple

from playwright.sync_api import Browser, Playwright, sync_playwright

from ..core.models import Step
from .element_locator import AIElementLocator
from .network_interceptor import NetworkInterceptor


class PlaywrightEngine:
    def __init__(self, browser_name: str = "chromium", headless: bool = True, timeout: int = 30000) -> None:
        self.browser_name = browser_name
        self.headless = headless
        self.timeout = timeout
        self._pw: Playwright | None = None
        self.browser: Browser | None = None
        self.page = None
        self.network = NetworkInterceptor()
        self.locator = AIElementLocator()

    def start(self) -> None:
        self._pw = sync_playwright().start()
        browser_type = getattr(self._pw, self.browser_name)
        self.browser = browser_type.launch(headless=self.headless)
        context = self.browser.new_context(accept_downloads=True)
        self.page = context.new_page()
        self.page.set_default_timeout(self.timeout)
        self.network.attach(self.page)

    def stop(self) -> None:
        if self.browser:
            self.browser.close()
            self.browser = None
        if self._pw:
            self._pw.stop()
            self._pw = None

    def open(self, url: str, base_url: str = "") -> None:
        target = url if url.startswith(("http://", "https://")) else base_url.rstrip("/") + "/" + url.lstrip("/")
        self.page.goto(target, wait_until="domcontentloaded")

    def run_step(self, step: Step):
        selector = step.selector or self.locator.find_element(self.page, step.description)
        action = step.action.lower()
        if action in {"type", "fill"}:
            self.page.locator(selector).fill(str(step.value))
        elif action == "click":
            self.page.locator(selector).click()
        elif action == "select":
            self.page.locator(selector).select_option(str(step.value))
        elif action == "upload":
            value = Path(str(step.value))
            if not value.exists():
                raise FileNotFoundError(f"Upload file not found: {value}")
            self.page.locator(selector).set_input_files(str(value))
        elif action == "wait":
            if selector:
                self.page.locator(selector).wait_for(state="visible", timeout=step.timeout)
            else:
                self.page.wait_for_timeout(step.timeout)
        elif action == "goto":
            self.open(str(step.value))
        else:
            raise ValueError(f"Unsupported step action: {step.action}")

    def response_text(self) -> str:
        selectors = [".result-container", ".result-text", "[data-testid='result']", "main"]
        for selector in selectors:
            loc = self.page.locator(selector)
            if loc.count() > 0:
                text = loc.first.inner_text().strip()
                if text:
                    return text
        return self.page.locator("body").inner_text().strip()

    def screenshot(self, path: str) -> str:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(destination), full_page=True)
        return str(destination)

    def errors(self) -> Tuple[list[str], list[str]]:
        return self.network.snapshot()
