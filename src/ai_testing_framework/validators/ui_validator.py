from __future__ import annotations

import time
from typing import Tuple


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


def validate_url_contains(page, expected: str) -> Tuple[bool, str]:
    actual = page.url
    ok = expected in actual
    return ok, f"Expected URL to contain {expected!r}; actual {actual!r}"
