from __future__ import annotations

from typing import Tuple


def validate_element_present(page, selector: str) -> Tuple[bool, str]:
    count = page.locator(selector).count()
    return count > 0, f"Element count: {count}"


def validate_text_contains(page, selector: str, expected: str) -> Tuple[bool, str]:
    if page.locator(selector).count() == 0:
        return False, f"Element not found: {selector}"
    actual = page.locator(selector).first.inner_text()
    ok = expected.lower() in actual.lower()
    return ok, f"Expected {expected!r}; actual {actual[:300]!r}"


def validate_url_contains(page, expected: str) -> Tuple[bool, str]:
    actual = page.url
    ok = expected in actual
    return ok, f"Expected URL to contain {expected!r}; actual {actual!r}"
