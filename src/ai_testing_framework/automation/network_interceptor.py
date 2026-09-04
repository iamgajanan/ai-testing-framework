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
        # Never read response bodies from inside the response event handler.
        # response.text() is synchronous and can block the page event loop,
        # preventing fetch/XHR callbacks from completing. Store the response
        # and capture its body later from response_snapshot().
        try:
            content_type = response.headers.get("content-type", "")
            item = NetworkResponse(
                url=response.url,
                method=response.request.method,
                status=response.status,
                status_text=response.status_text,
                content_type=content_type,
            )
            self.responses.append(item)
            self._response_objects.append(response)
            if response.status >= 400:
                self.api_errors.append(
                    f"{response.status} {response.request.method} {response.url}"
                )
        except Exception:
            pass

    def _request_failed(self, request) -> None:
        self.api_errors.append(f"FAILED {request.method} {request.url}: {request.failure}")

    def snapshot(self) -> Tuple[List[str], List[str]]:
        return list(self.console_errors), list(self.api_errors)

    def response_snapshot(self) -> List[dict[str, Any]]:
        for index, response in enumerate(self._response_objects):
            if index >= len(self.responses):
                break
            item = self.responses[index]
            if item.body or item.json is not None:
                continue
            try:
                content_type = item.content_type.lower()
                readable = any(
                    kind in content_type
                    for kind in ("json", "text/", "javascript", "xml", "form-urlencoded")
                )
                if not readable:
                    continue
                body = response.text()
                item.body = body
                if "json" in content_type and body:
                    try:
                        item.json = json.loads(body)
                    except (ValueError, TypeError):
                        pass
            except Exception:
                # Body capture is best-effort; the response metadata remains
                # available for status/URL/method assertions.
                continue
        return [response.to_dict() for response in self.responses]

    def reset(self) -> None:
        self.console_errors.clear()
        self.api_errors.clear()
        self.responses.clear()
        self._response_objects.clear()
