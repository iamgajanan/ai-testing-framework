from __future__ import annotations

from dataclasses import dataclass, asdict
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
            body = response.text()
            parsed_json = None
            if "json" in content_type.lower():
                try:
                    import json
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
                self.api_errors.append(f"{response.status} {response.request.method} {response.url}")
        except Exception as exc:
            self.api_errors.append(f"RESPONSE_CAPTURE_FAILED {response.url}: {exc}")

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
