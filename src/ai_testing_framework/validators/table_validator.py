from __future__ import annotations

import re


def validate_table(page, selector: str | None, expected_columns: list[str], row_condition: str | None = None) -> tuple[bool, str]:
    table = page.locator(selector or "table").first
    if table.count() == 0:
        return False, "Table not found"
    headers = [h.strip() for h in table.locator("thead th").all_inner_texts()]
    if not headers:
        headers = [h.strip() for h in table.locator("tr").first.locator("th,td").all_inner_texts()]
    missing = [column for column in expected_columns if column.lower() not in {h.lower() for h in headers}]
    if missing:
        return False, f"Missing columns: {missing}; found: {headers}"
    rows = table.locator("tbody tr")
    if rows.count() == 0:
        rows = table.locator("tr").nth(1)
    if row_condition and rows.count() > 0:
        match = re.search(r"([\w ]+)\s+(?:should\s+equal|=)\s*['\"]?([^'\"]+)['\"]?", row_condition, re.I)
        if match:
            column, expected = match.group(1).strip(), match.group(2).strip()
            try:
                index = next(i for i, h in enumerate(headers) if h.lower() == column.lower())
            except StopIteration:
                return False, f"Condition column not found: {column}"
            all_rows = table.locator("tbody tr").all()
            if not all_rows:
                return False, "Table has no data rows"
            bad = []
            for i, row in enumerate(all_rows):
                cells = row.locator("td").all_inner_texts()
                if index >= len(cells) or cells[index].strip().lower() != expected.lower():
                    bad.append(i + 1)
            if bad:
                return False, f"Rows failing condition: {bad}"
    return True, f"Table headers valid: {headers}"
