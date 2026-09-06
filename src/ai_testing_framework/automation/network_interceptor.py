from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
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
    request_headers: dict[str, str] = field(default_factory=dict)
    response_headers: dict[str, str] = field(default_factory=dict)
    request_body: Any = None
    response_time_ms: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class NetworkInterceptor:
    def __init__(self) -> None:
        self.console_errors: List[str] = []
        self.api_errors: List[str] = []
        self.responses: List[NetworkResponse] = []
        self._response_objects: List[Response] = []
        self._request_starts: dict[int, float] = {}

    def attach(self, page: Page) -> None:
        page.on("console", self._console)
        page.on("request", self._request)
        page.on("response", self._response)
        page.on("requestfailed", self._request_failed)

    def _console(self, message) -> None:
        if message.type == "error":
            self.console_errors.append(message.text)

    def _request(self, request) -> None:
        self._request_starts[id(request)] = time.perf_counter()

    def _response(self, response: Response) -> None:
        # Do not read protocol properties in the response callback; defer all
        # body/header access until the runner asks for a snapshot.
        self._response_objects.append(response)

    def _request_failed(self, request) -> None:
        self.api_errors.append(f"FAILED {request.method} {request.url}: {request.failure}")
        self._request_starts.pop(id(request), None)

    def snapshot(self) -> Tuple[List[str], List[str]]:
        return list(self.console_errors), list(self.api_errors)

    def response_snapshot(self) -> List[dict[str, Any]]:
        self.responses = []
        for response in self._response_objects:
            try:
                request = response.request
                started = self._request_starts.get(id(request))
                elapsed = (time.perf_counter() - started) * 1000 if started else None
                req_headers = dict(request.all_headers())
                resp_headers = dict(response.all_headers())
                post_data = request.post_data
                request_body: Any = post_data
                if post_data:
                    try:
                        request_body = json.loads(post_data)
                    except (ValueError, TypeError):
                        pass

                item = NetworkResponse(
                    url=response.url,
                    method=request.method,
                    status=response.status,
                    status_text=response.status_text,
                    request_headers=req_headers,
                    response_headers=resp_headers,
                    request_body=request_body,
                    response_time_ms=elapsed,
                )
                content_type = resp_headers.get("content-type", "")
                item.content_type = content_type
                readable = any(
                    kind in content_type.lower()
                    for kind in ("json", "text/", "javascript", "xml", "form-urlencoded")
                )
                if readable:
                    body = response.text()
                    item.body = body
                    if body:
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
                continue
        return [response.to_dict() for response in self.responses]

    def reset(self) -> None:
        self.console_errors.clear()
        self.api_errors.clear()
        self.responses.clear()
        self._response_objects.clear()
        self._request_starts.clear()
