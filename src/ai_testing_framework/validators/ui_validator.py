from __future__ import annotations

import time
from typing import Any, Tuple


def validate_element_present(page, selector: str) -> Tuple[bool, str]:
    count = page.locator(selector).count()
    return count > 0, f"Element count: {count}"


def validate_text_contains(page, selector: str, expected: str, timeout: int = 5000, poll_interval: int = 100) -> Tuple[bool, str]:
    """Validate text while allowing asynchronous UI updates to settle."""
    deadline = time.monotonic() + max(0, timeout) / 1000
    actual = ""
    while True:
        locator = page.locator(selector)
        if locator.count() == 0:
            return False, f"Element not found: {selector}"
        actual = locator.first.inner_text()
        if expected.lower() in actual.lower():
            return True, f"Expected {expected!r}; actual {actual[:300]!r}"
        if time.monotonic() >= deadline:
            return False, f"Expected {expected!r}; actual {actual[:300]!r}"
        page.wait_for_timeout(min(poll_interval, max(1, int((deadline - time.monotonic()) * 1000))))


def _first(page, selector: str):
    locator = page.locator(selector)
    if locator.count() == 0:
        return None
    return locator.first


def validate_element_attribute(page, selector: str, attribute: str, expected: Any) -> Tuple[bool, str]:
    """Validate an element attribute using Playwright's DOM property access."""
    locator = _first(page, selector)
    if locator is None:
        return False, f"Element not found: {selector}"
    actual = locator.get_attribute(attribute)
    # Boolean HTML attributes are represented as present/absent attributes.
    if isinstance(expected, bool):
        actual_value = actual is not None
        return actual_value == expected, f"Expected attribute {attribute!r}={expected!r}; actual={actual_value!r}"
    return str(actual) == str(expected), f"Expected attribute {attribute!r}={expected!r}; actual={actual!r}"


def validate_element_value(page, selector: str, expected: Any) -> Tuple[bool, str]:
    locator = _first(page, selector)
    if locator is None:
        return False, f"Element not found: {selector}"
    actual = locator.input_value()
    return str(actual) == str(expected), f"Expected value {expected!r}; actual={actual!r}"


def validate_element_state(page, selector: str, state: str, expected: bool = True) -> Tuple[bool, str]:
    locator = _first(page, selector)
    if locator is None:
        return False, f"Element not found: {selector}"
    state = state.lower().strip()
    checks = {
        "visible": locator.is_visible,
        "hidden": lambda: not locator.is_visible(),
        "enabled": locator.is_enabled,
        "disabled": lambda: not locator.is_enabled(),
        "checked": locator.is_checked,
        "unchecked": lambda: not locator.is_checked(),
        "editable": locator.is_editable,
    }
    if state not in checks:
        raise ValueError(f"Unsupported element state: {state!r}")
    actual = bool(checks[state]())
    expected = bool(expected)
    return actual == expected, f"Expected {state}={expected}; actual={actual}"


def validate_element_count(page, selector: str, expected: int) -> Tuple[bool, str]:
    actual = page.locator(selector).count()
    return actual == int(expected), f"Expected element count {expected}; actual={actual}"


def validate_url_contains(page, expected: str) -> Tuple[bool, str]:
    actual = page.url
    ok = expected in actual
    return ok, f"Expected URL to contain {expected!r}; actual {actual!r}"
