from __future__ import annotations

from typing import List, Tuple

from playwright.sync_api import Page, Response


class NetworkInterceptor:
    def __init__(self) -> None:
        self.console_errors: List[str] = []
        self.api_errors: List[str] = []

    def attach(self, page: Page) -> None:
        page.on("console", self._console)
        page.on("response", self._response)
        page.on("requestfailed", self._request_failed)

    def _console(self, message) -> None:
        if message.type == "error":
            self.console_errors.append(message.text)

    def _response(self, response: Response) -> None:
        if response.status >= 400:
            self.api_errors.append(f"{response.status} {response.request.method} {response.url}")

    def _request_failed(self, request) -> None:
        self.api_errors.append(f"FAILED {request.method} {request.url}: {request.failure}")

    def snapshot(self) -> Tuple[List[str], List[str]]:
        return list(self.console_errors), list(self.api_errors)
