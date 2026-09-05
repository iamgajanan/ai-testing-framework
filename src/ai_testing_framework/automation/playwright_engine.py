from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from .element_locator import AIElementLocator
from .self_healing import SelfHealing


class PlaywrightEngine:
    """Thin synchronous Playwright adapter used by the test runner."""

    def __init__(
        self,
        browser_name: str = "chromium",
        headless: bool = True,
        timeout: int = 30000,
        ai_provider: str = "none",
        ai_model: str = "gpt-4o-mini",
        self_healing: bool = True,
        healing_confidence: float = 0.70,
    ) -> None:
        self.browser_name = browser_name
        self.headless = headless
        self.timeout = timeout
        self.ai_locator = AIElementLocator(ai_provider, ai_model)
        self.self_healing = (
            SelfHealing(ai_provider, ai_model, healing_confidence) if self_healing else None
        )
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.console_errors: list[str] = []
        self.api_errors: list[str] = []
        self.downloads: list[str] = []
        self.healed_selectors: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

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
        self.page.on(
            "console",
            lambda msg: self.console_errors.append(msg.text) if msg.type == "error" else None,
        )
        self.page.on(
            "requestfailed",
            lambda request: self.api_errors.append(
                f"{request.method} {request.url}: {request.failure}"
            ),
        )

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def open(self, url: str, base_url: str = "") -> None:
        assert self.page is not None
        target = (
            f"{base_url.rstrip('/')}/{url.lstrip('/')}"
            if base_url and url.startswith("/")
            else url
        )
        self.page.goto(target, wait_until="domcontentloaded")

    # ------------------------------------------------------------------
    # Selector resolution with self-healing
    # ------------------------------------------------------------------

    def _resolve_locator(self, selector: str | None, description: str = ""):
        """Return a Playwright Locator for the given selector or description.

        Resolution order:
        1. selector present  → use it directly.
           If the selector fails at action time and self-healing is enabled,
           the engine will attempt to recover (see _try_heal).
        2. description only  → use AIElementLocator to find an element.
        3. neither           → raise ValueError.

        We deliberately do NOT call locator.count() here because:
        - It triggers a Playwright protocol round-trip (wrong place for it).
        - It returns a Mock in unit tests, causing TypeError on comparison.
        Self-healing is invoked lazily from _try_heal() when an action raises.
        """
        assert self.page is not None
        if selector:
            return self.page.locator(selector)
        if description:
            return self.ai_locator.find_element(self.page, description)
        raise ValueError("Step requires either 'selector' or 'description'.")

    def _try_heal(self, selector: str, description: str, action_fn, timeout: int):
        """Execute action_fn; on failure attempt self-healing then retry once."""
        locator = self.page.locator(selector)
        try:
            return action_fn(locator)
        except Exception as original:
            if not self.self_healing:
                raise
            healed_selector = self.self_healing.heal_selector(
                self.page, selector, description
            )
            if healed_selector:
                self.healed_selectors.append(
                    {
                        "failed_selector": selector,
                        "healed_selector": healed_selector,
                        "reason": self.self_healing.last_reason,
                        "confidence": self.self_healing.last_confidence,
                    }
                )
                return action_fn(self.page.locator(healed_selector))
            raise original

    # ------------------------------------------------------------------
    # Step execution
    # ------------------------------------------------------------------

    def run_step(self, step: Any) -> Any:
        assert self.page is not None
        action = step.action.lower().strip()
        selector: Optional[str] = step.selector
        description: str = getattr(step, "description", "") or ""
        value: str = "" if step.value is None else str(step.value)
        timeout: int = getattr(step, "timeout", self.timeout)

        # Special case: press/keyboard with no selector → global keyboard event.
        if action in {"press", "keyboard"} and not selector and not description:
            self.page.keyboard.press(value)
            return

        if action == "wait_for_load_state":
            self.page.wait_for_load_state(value or "networkidle", timeout=timeout)
            return

        locator = self._resolve_locator(selector, description)

        if action in {"type", "fill"}:
            if selector and self.self_healing:
                self._try_heal(selector, description, lambda l: l.fill(value, timeout=timeout), timeout)
            else:
                locator.fill(value, timeout=timeout)

        elif action == "click":
            if selector and self.self_healing:
                self._try_heal(selector, description, lambda l: l.click(timeout=timeout), timeout)
            else:
                locator.click(timeout=timeout)

        elif action in {"check", "checkbox"}:
            if selector and self.self_healing:
                self._try_heal(selector, description, lambda l: l.check(timeout=timeout), timeout)
            else:
                locator.check(timeout=timeout)

        elif action == "uncheck":
            if selector and self.self_healing:
                self._try_heal(selector, description, lambda l: l.uncheck(timeout=timeout), timeout)
            else:
                locator.uncheck(timeout=timeout)

        elif action in {"select", "select_option"}:
            if selector and self.self_healing:
                self._try_heal(selector, description, lambda l: l.select_option(value, timeout=timeout), timeout)
            else:
                locator.select_option(value, timeout=timeout)

        elif action == "hover":
            if selector and self.self_healing:
                self._try_heal(selector, description, lambda l: l.hover(timeout=timeout), timeout)
            else:
                locator.hover(timeout=timeout)

        elif action in {"press", "keyboard"}:
            # selector or description is set (no-selector case handled above)
            if selector and self.self_healing:
                self._try_heal(selector, description, lambda l: l.press(value, timeout=timeout), timeout)
            else:
                locator.press(value, timeout=timeout)

        elif action in {"upload", "set_input_files"}:
            if selector and self.self_healing:
                self._try_heal(selector, description, lambda l: l.set_input_files(value, timeout=timeout), timeout)
            else:
                locator.set_input_files(value, timeout=timeout)

        elif action in {"wait", "wait_for_selector"}:
            if selector and self.self_healing:
                self._try_heal(selector, description, lambda l: l.wait_for(state="visible", timeout=timeout), timeout)
            else:
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

        else:
            raise ValueError(f"Unsupported Playwright action: {step.action!r}")

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

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
