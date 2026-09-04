from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, List, Tuple

from playwright.sync_api import Page, Response


@dataclass
class NetworkResponse:
    url: str
    method: str
    status: int
    status_text: str = ""
    content_type: str = ""
    body: str = ""
    json: Any = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class NetworkInterceptor:
    def __init__(self) -> None:
        self.console_errors: List[str] = []
        self.api_errors: List[str] = []
        self.responses: List[NetworkResponse] = []
        self._response_objects: List[Response] = []

    def attach(self, page: Page) -> None:
        page.on("console", self._console)
        page.on("response", self._response)
        page.on("requestfailed", self._request_failed)

    def _console(self, message) -> None:
        if message.type == "error":
            self.console_errors.append(message.text)

    def _response(self, response: Response) -> None:
        # Never read Playwright protocol properties from a response callback.
        # In the sync API, doing so can block the browser event loop while the
        # page is waiting for the same response to resume its fetch/XHR code.
        # Keep only the object reference and inspect it later from the runner.
        self._response_objects.append(response)

    def _request_failed(self, request) -> None:
        self.api_errors.append(f"FAILED {request.method} {request.url}: {request.failure}")

    def snapshot(self) -> Tuple[List[str], List[str]]:
        return list(self.console_errors), list(self.api_errors)

    def response_snapshot(self) -> List[dict[str, Any]]:
        # Build metadata lazily, outside the response event callback.
        self.responses = []
        for response in self._response_objects:
            try:
                item = NetworkResponse(
                    url=response.url,
                    method=response.request.method,
                    status=response.status,
                    status_text=response.status_text,
                )
                content_type = response.headers.get("content-type", "")
                item.content_type = content_type

                readable = any(
                    kind in content_type.lower()
                    for kind in ("json", "text/", "javascript", "xml", "form-urlencoded")
                )
                if readable:
                    body = response.text()
                    item.body = body
                    if "json" in content_type.lower() and body:
                        try:
                            item.json = json.loads(body)
                        except (ValueError, TypeError):
                            pass

                if item.status >= 400:
                    error = f"{item.status} {item.method} {item.url}"
                    if error not in self.api_errors:
                        self.api_errors.append(error)

                self.responses.append(item)
            except Exception:
                # Ignore responses whose metadata/body is no longer available.
                continue

        return [response.to_dict() for response in self.responses]

    def reset(self) -> None:
        self.console_errors.clear()
        self.api_errors.clear()
        self.responses.clear()
        self._response_objects.clear()
