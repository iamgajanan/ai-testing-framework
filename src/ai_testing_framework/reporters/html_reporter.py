from __future__ import annotations

import html
from pathlib import Path
from typing import Iterable

from ..core.models import TestResult


def write_html_report(results: Iterable[TestResult], output_dir: str = "reports") -> str:
    results = list(results)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    passed = sum(r.status == "PASS" for r in results)
    failed = len(results) - passed
    cards = []

    for r in results:
        validation_items = []
        for v in r.validations:
            css_class = "pass" if v.passed else "fail"
            confidence = f" (confidence {v.confidence:.2f})" if v.confidence is not None else ""
            validation_items.append(
                f"<li class='{css_class}'>{html.escape(v.type)} — "
                f"{html.escape(v.reason)}{confidence}</li>"
            )
        validations = "".join(validation_items)

        screenshot = (
            f"<p><a href='{html.escape(r.screenshot)}'>Failure screenshot</a></p>"
            if r.screenshot
            else ""
        )

        diagnostics = ""
        if getattr(r, "healed_selectors", []):
            rows = "".join(
                f"<tr><td><code>{html.escape(h['failed_selector'])}</code></td>"
                f"<td><code>{html.escape(h['healed_selector'])}</code></td>"
                f"<td>{html.escape(h.get('reason', ''))}</td>"
                f"<td>{h.get('confidence', 0):.2f}</td></tr>"
                for h in r.healed_selectors
            )
            diagnostics += (
                "<h4>⚕️ Self-healed selectors</h4>"
                "<table border='1' cellpadding='4' style='border-collapse:collapse;font-size:0.9em'>"
                "<thead><tr><th>Failed selector</th><th>Healed selector</th>"
                "<th>Reason</th><th>Confidence</th></tr></thead>"
                f"<tbody>{rows}</tbody></table>"
            )
        if r.console_errors:
            diagnostics += (
                "<h4>Console errors</h4><pre>"
                + html.escape("\n".join(r.console_errors))
                + "</pre>"
            )
        if r.api_errors:
            diagnostics += (
                "<h4>Network errors</h4><pre>"
                + html.escape("\n".join(r.api_errors))
                + "</pre>"
            )

        error_html = (
            f"<p>Error: {html.escape(r.error)}</p>" if r.error else ""
        )
        status_text = "✅ PASSED" if r.status == "PASS" else "❌ FAILED"
        status_class = r.status.lower()

        cards.append(
            f"<section class='test'><h2>{html.escape(r.id)}: {html.escape(r.name)}</h2>"
            f"<span class='badge {status_class}'>{status_text}</span>"
            f"<p>Duration: {r.duration:.2f}s</p>"
            f"<p>Response: <code>{html.escape(r.response[:2000])}</code></p>"
            f"{error_html}{screenshot}<ul>{validations}</ul>{diagnostics}</section>"
        )

    page = f"""<!doctype html>
<html>
<head>
<meta charset='utf-8'>
<title>AI Test Report</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:1100px;margin:40px auto;padding:0 20px;background:#f6f7f9}}
.summary,.test{{background:white;padding:20px;margin:16px 0;border-radius:12px;box-shadow:0 1px 5px #ddd}}
.badge{{padding:4px 10px;border-radius:999px;font-weight:700}}
.pass{{color:#137333}}.fail{{color:#b3261e}}
.passed{{background:#e6f4ea;color:#137333}}.failed{{background:#fce8e6;color:#b3261e}}
pre{{overflow:auto;background:#f1f3f4;padding:12px;border-radius:8px}}
code{{white-space:pre-wrap}}
</style>
</head>
<body>
<h1>AI Test Execution Report</h1>
<div class='summary'><h2>Summary</h2><p>Total: {len(results)} | Passed: {passed} | Failed: {failed}</p></div>
{''.join(cards)}
</body>
</html>"""

    target = out / "test_report.html"
    target.write_text(page, encoding="utf-8")
    return str(target)
