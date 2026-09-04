import re


def validate_regex(response: str, pattern: str) -> tuple[bool, str]:
    try:
        matched = re.search(pattern, response or "") is not None
    except re.error as exc:
        return False, f"Invalid regex: {exc}"
    return matched, "Regex matched" if matched else f"Regex did not match: {pattern}"
