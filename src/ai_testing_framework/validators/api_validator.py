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
        return urlparse(actual).path == expected or urlparse(actual).path.startswith(expected.rstrip("/") + "/")
    return expected in actual


def _equal(actual: Any, expected: Any) -> bool:
    if isinstance(actual, str) and not isinstance(expected, str):
        try:
            actual = json.loads(actual)
        except (ValueError, TypeError):
            pass
    return actual == expected


def _headers_match(actual: dict[str, Any], expected: dict[str, Any]) -> tuple[bool, str]:
    normalized = {str(k).lower(): str(v) for k, v in (actual or {}).items()}
    for key, value in (expected or {}).items():
        if normalized.get(str(key).lower()) != str(value):
            return False, f"Header {key!r} expected {value!r}, got {normalized.get(str(key).lower())!r}"
    return True, ""


def _schema_validate(value: Any, schema: dict[str, Any], path: str = "$", errors: list[str] | None = None) -> list[str]:
    errors = errors if errors is not None else []
    typ = schema.get("type")
    type_ok = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }
    if typ in type_ok and not type_ok[typ]:
        errors.append(f"{path} expected {typ}, got {type(value).__name__}")
        return errors
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path} must be one of {schema['enum']!r}")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key} is required")
        for key, child in schema.get("properties", {}).items():
            if key in value and isinstance(child, dict):
                _schema_validate(value[key], child, f"{path}.{key}", errors)
        if schema.get("additionalProperties") is False:
            allowed = set(schema.get("properties", {}))
            for key in value:
                if key not in allowed:
                    errors.append(f"{path}.{key} is not allowed")
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for i, item in enumerate(value):
            _schema_validate(item, schema["items"], f"{path}[{i}]", errors)
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path} length is below {schema['minLength']}")
        if "pattern" in schema:
            import re
            if not re.search(schema["pattern"], value):
                errors.append(f"{path} does not match pattern")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path} is below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path} is above maximum {schema['maximum']}")
    return errors


def validate_api_response(
    responses: Iterable[dict[str, Any]],
    *,
    url: str = "",
    method: str = "",
    status: int | None = None,
    request_headers: dict[str, str] | None = None,
    response_headers: dict[str, str] | None = None,
    request_body: Any = None,
    response_body: Any = None,
    json_schema: dict[str, Any] | None = None,
    response_time_ms: float | None = None,
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
    if request_headers:
        matches = [r for r in matches if _headers_match(r.get("request_headers", {}), request_headers)[0]]
    if not matches:
        return False, f"No API response matched url={url!r}, method={method or '*'}, status={status if status is not None else '*'}", None

    response = matches[-1]
    if response_headers:
        ok, reason = _headers_match(response.get("response_headers", {}), response_headers)
        if not ok:
            return False, reason, response

    if request_body is not None and not _equal(response.get("request_body"), request_body):
        return False, f"Request body expected {request_body!r}, got {response.get('request_body')!r}", response

    data = response.get("json")
    if data is None and response.get("body"):
        try:
            data = json.loads(response["body"])
        except (ValueError, TypeError):
            pass

    if response_body is not None:
        actual_body = data if data is not None else response.get("body", "")
        if not _equal(actual_body, response_body):
            return False, f"Response body expected {response_body!r}, got {actual_body!r}", response

    if json_path:
        if data is None:
            return False, "Matched API response is not valid JSON", response
        try:
            actual = _json_path(data, json_path)
        except (KeyError, IndexError):
            return False, f"JSON path not found: {json_path}", response
        if not _equal(actual, expected):
            return False, f"JSON {json_path!r} expected {expected!r}, got {actual!r}", response

    if json_schema:
        if data is None:
            return False, "Matched API response is not valid JSON for schema validation", response
        errors = _schema_validate(data, json_schema)
        if errors:
            return False, "JSON schema validation failed: " + "; ".join(errors[:5]), response

    if body_contains and body_contains.lower() not in str(response.get("body", "")).lower():
        return False, f"Response body does not contain {body_contains!r}", response

    if response_time_ms is not None:
        actual_time = response.get("response_time_ms")
        if actual_time is None:
            return False, "Response timing data is unavailable", response
        if float(actual_time) > float(response_time_ms):
            return False, f"Response took {actual_time:.1f}ms, exceeds limit {response_time_ms:.1f}ms", response

    return True, f"API assertion passed: {response.get('status')} {response.get('method')} {response.get('url')}", response
