from __future__ import annotations

import json
from typing import Any, Iterable
from urllib.parse import urlparse


def _json_path(data: Any, path: str) -> Any:
    current = data
    for part in path.split("."):
        if not part:
            continue
        if isinstance(current, dict):
            if part not in current:
                raise KeyError(part)
            current = current[part]
        elif isinstance(current, list) and part.isdigit():
            current = current[int(part)]
        else:
            raise KeyError(path)
    return current


def _matches_url(actual: str, expected: str) -> bool:
    if not expected:
        return True
    if expected.startswith("/"):
        return urlparse(actual).path == expected or urlparse(actual).path.startswith(expected)
    return expected in actual


def _equal(actual: Any, expected: Any) -> bool:
    if isinstance(actual, str) and not isinstance(expected, str):
        try:
            actual = json.loads(actual)
        except (ValueError, TypeError):
            pass
    return actual == expected


def validate_api_response(
    responses: Iterable[dict[str, Any]],
    *,
    url: str = "",
    method: str = "",
    status: int | None = None,
    json_path: str = "",
    expected: Any = None,
    body_contains: str = "",
) -> tuple[bool, str, dict[str, Any] | None]:
    candidates = list(responses)
    matches = [r for r in candidates if _matches_url(str(r.get("url", "")), url)]
    if method:
        matches = [r for r in matches if str(r.get("method", "")).upper() == method.upper()]
    if status is not None:
        matches = [r for r in matches if int(r.get("status", -1)) == int(status)]

    if not matches:
        return False, f"No API response matched url={url!r}, method={method or '*'}, status={status if status is not None else '*'}", None

    response = matches[-1]
    if json_path:
        data = response.get("json")
        if data is None:
            try:
                data = json.loads(response.get("body", ""))
            except (ValueError, TypeError):
                return False, "Matched API response is not valid JSON", response
        try:
            actual = _json_path(data, json_path)
        except KeyError:
            return False, f"JSON path not found: {json_path}", response
        if not _equal(actual, expected):
            return False, f"JSON {json_path!r} expected {expected!r}, got {actual!r}", response

    if body_contains and body_contains.lower() not in str(response.get("body", "")).lower():
        return False, f"Response body does not contain {body_contains!r}", response

    return True, f"API assertion passed: {response.get('status')} {response.get('method')} {response.get('url')}", response
