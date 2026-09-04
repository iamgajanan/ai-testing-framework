from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, List, Optional, Tuple

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

    def attach(self, page: Page) -> None:
        page.on("console", self._console)
        page.on("response", self._response)
        page.on("requestfailed", self._request_failed)

    def _console(self, message) -> None:
        if message.type == "error":
            self.console_errors.append(message.text)

    def _response(self, response: Response) -> None:
        try:
            content_type = response.headers.get("content-type", "")
            content_type_lower = content_type.lower()
            body = ""
            parsed_json = None

            # Only read bodies that are useful for API/text assertions.
            # Binary assets can disappear from the browser protocol before
            # response.text() is called and must not become false API errors.
            readable = any(
                kind in content_type_lower
                for kind in ("json", "text/", "javascript", "xml", "form-urlencoded")
            )
            if readable:
                try:
                    body = response.text()
                except Exception:
                    body = ""

            if "json" in content_type_lower and body:
                try:
                    parsed_json = json.loads(body)
                except (ValueError, TypeError):
                    pass

            self.responses.append(NetworkResponse(
                url=response.url,
                method=response.request.method,
                status=response.status,
                status_text=response.status_text,
                content_type=content_type,
                body=body,
                json=parsed_json,
            ))
            if response.status >= 400:
                self.api_errors.append(
                    f"{response.status} {response.request.method} {response.url}"
                )
        except Exception as exc:
            # Capture bookkeeping failures without turning a valid response
            # into a test/network failure.
            self.responses.append(NetworkResponse(
                url=response.url,
                method=response.request.method,
                status=response.status,
                status_text=response.status_text,
            ))

    def _request_failed(self, request) -> None:
        self.api_errors.append(f"FAILED {request.method} {request.url}: {request.failure}")

    def snapshot(self) -> Tuple[List[str], List[str]]:
        return list(self.console_errors), list(self.api_errors)

    def response_snapshot(self) -> List[dict[str, Any]]:
        return [response.to_dict() for response in self.responses]

    def reset(self) -> None:
        self.console_errors.clear()
        self.api_errors.clear()
        self.responses.clear()
