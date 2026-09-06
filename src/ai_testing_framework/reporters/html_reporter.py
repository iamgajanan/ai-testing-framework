"""HTML reporter for the Universal AI Testing Framework — Phase 5.

Produces a single self-contained HTML file with:
- Summary dashboard (pass rate, total duration, suite name)
- Per-test cards with: status badge, duration, step trace, validation detail,
  AI-location events, self-healing table, inline base64 screenshots,
  console errors, network errors
- No external CSS/JS dependencies (fully offline-capable)
"""
from __future__ import annotations

import base64
import html as _html
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from ..core.models import TestResult
from ..ai.failure_analyzer import FailureAnalyzer

# ---------------------------------------------------------------------------
# CSS (single string, injected into <style>)
# ---------------------------------------------------------------------------

_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: system-ui, -apple-system, sans-serif;
  font-size: 14px;
  background: #f0f2f5;
  color: #1a1a2e;
  padding: 32px 20px;
}
h1 { font-size: 1.6rem; font-weight: 700; margin-bottom: 4px; color: #1a1a2e; }
h2 { font-size: 1.1rem; font-weight: 600; margin-bottom: 12px; }
h3 { font-size: 0.95rem; font-weight: 600; color: #444; margin: 16px 0 8px; text-transform: uppercase; letter-spacing: 0.04em; }
.subtitle { color: #666; font-size: 0.85rem; margin-bottom: 28px; }
.card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0,0,0,.08);
  padding: 20px 24px;
  margin-bottom: 16px;
}
/* Summary dashboard */
.dashboard { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }
.stat {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0,0,0,.08);
  padding: 16px 24px;
  flex: 1;
  min-width: 140px;
  text-align: center;
}
.stat .value { font-size: 2rem; font-weight: 700; line-height: 1; }
.stat .label { font-size: 0.78rem; color: #888; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.06em; }
.stat.pass .value { color: #137333; }
.stat.fail .value { color: #b3261e; }
.stat.total .value { color: #1a73e8; }
.stat.dur .value { font-size: 1.5rem; color: #555; }
/* Pass rate bar */
.rate-bar-wrap { background: #e8eaed; border-radius: 999px; height: 8px; margin: 8px 0 4px; overflow: hidden; }
.rate-bar { height: 100%; border-radius: 999px; background: #137333; transition: width .4s; }
.rate-label { font-size: 0.82rem; color: #555; text-align: right; }
/* Test card */
.test-card { border-left: 4px solid #e0e0e0; }
.test-card.pass { border-left-color: #34a853; }
.test-card.fail { border-left-color: #ea4335; }
.test-header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.test-id { font-family: monospace; font-size: 0.85rem; background: #f1f3f4; padding: 2px 8px; border-radius: 6px; }
.test-name { flex: 1; font-weight: 600; font-size: 1rem; }
.badge {
  padding: 3px 12px; border-radius: 999px; font-weight: 700; font-size: 0.8rem;
  white-space: nowrap;
}
.badge.pass { background: #e6f4ea; color: #137333; }
.badge.fail { background: #fce8e6; color: #b3261e; }
.dur-badge { font-size: 0.78rem; color: #888; }
/* Sections within a test card */
.section { margin-top: 14px; padding-top: 14px; border-top: 1px solid #f0f0f0; }
/* Validations */
.val-list { list-style: none; }
.val-list li { display: flex; align-items: flex-start; gap: 8px; padding: 5px 0; border-bottom: 1px solid #f8f8f8; font-size: 0.88rem; }
.val-list li:last-child { border-bottom: none; }
.val-icon { flex-shrink: 0; font-size: 1rem; }
.val-type { font-family: monospace; font-size: 0.8rem; background: #f1f3f4; padding: 1px 6px; border-radius: 4px; white-space: nowrap; }
.val-reason { color: #444; flex: 1; }
.val-conf { font-size: 0.78rem; color: #888; white-space: nowrap; }
/* Self-healing table */
.heal-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.heal-table th { background: #fff8e1; color: #7c5700; font-weight: 600; padding: 6px 10px; text-align: left; border-bottom: 2px solid #ffe082; }
.heal-table td { padding: 6px 10px; border-bottom: 1px solid #f5f5f5; vertical-align: top; }
.heal-table tr:last-child td { border-bottom: none; }
.heal-table code { font-family: monospace; font-size: 0.82rem; background: #f1f3f4; padding: 1px 5px; border-radius: 4px; }
.conf-pill { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 0.76rem; font-weight: 600; }
.conf-high { background: #e6f4ea; color: #137333; }
.conf-med  { background: #fff8e1; color: #7c5700; }
.conf-low  { background: #fce8e6; color: #b3261e; }
/* Error blocks */
.error-msg { background: #fce8e6; border-left: 3px solid #ea4335; padding: 8px 12px; border-radius: 0 6px 6px 0; font-size: 0.87rem; color: #b3261e; margin-top: 8px; }
pre.diag { background: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 8px; padding: 12px; font-size: 0.82rem; overflow-x: auto; white-space: pre-wrap; word-break: break-all; max-height: 300px; overflow-y: auto; }
/* Screenshot */
.screenshot { margin-top: 12px; }
.screenshot summary { cursor: pointer; font-size: 0.85rem; color: #1a73e8; }
.screenshot img { max-width: 100%; border: 1px solid #e0e0e0; border-radius: 8px; margin-top: 8px; }
/* Collapsible */
details > summary { cursor: pointer; user-select: none; }
details > summary::-webkit-details-marker { display: none; }
details > summary::before { content: '▶ '; font-size: 0.7em; }
details[open] > summary::before { content: '▼ '; }
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _e(s: str) -> str:
    return _html.escape(str(s))

def _conf_pill(conf: float) -> str:
    cls = "conf-high" if conf >= 0.80 else ("conf-med" if conf >= 0.60 else "conf-low")
    return f"<span class='conf-pill {cls}'>{conf:.0%}</span>"

def _inline_screenshot(path: str) -> str:
    """Return an inline base64 <img> tag, or empty string on failure."""
    try:
        data = Path(path).read_bytes()
        b64 = base64.b64encode(data).decode()
        return (
            "<details class='screenshot'>"
            "<summary>📷 Failure screenshot</summary>"
            f"<img src='data:image/png;base64,{b64}' alt='screenshot'/>"
            "</details>"
        )
    except Exception:
        return f"<p><small>Screenshot: {_e(path)}</small></p>"

def _validation_list(validations) -> str:
    if not validations:
        return "<p style='color:#888;font-size:.85rem'>No validations recorded.</p>"
    items = []
    for v in validations:
        icon = "✅" if v.passed else "❌"
        conf = f"<span class='val-conf'>{_conf_pill(v.confidence)}</span>" if v.confidence is not None else ""
        actual = ""
        if not v.passed and v.actual is not None:
            actual = f"<br><span style='color:#888;font-size:.8rem'>Actual: {_e(str(v.actual)[:200])}</span>"
        items.append(
            f"<li>"
            f"<span class='val-icon'>{icon}</span>"
            f"<span class='val-type'>{_e(v.type)}</span>"
            f"<span class='val-reason'>{_e(v.reason)}{actual}</span>"
            f"{conf}"
            f"</li>"
        )
    return f"<ul class='val-list'>{''.join(items)}</ul>"

def _healing_table(healed: list) -> str:
    if not healed:
        return ""
    rows = []
    for h in healed:
        conf = float(h.get("confidence", 0))
        rows.append(
            f"<tr>"
            f"<td><code>{_e(h.get('failed_selector',''))}</code></td>"
            f"<td><code>{_e(h.get('healed_selector',''))}</code></td>"
            f"<td style='color:#555'>{_e(h.get('reason',''))}</td>"
            f"<td>{_conf_pill(conf)}</td>"
            f"</tr>"
        )
    return (
        "<h3>⚕️ Self-healed selectors</h3>"
        "<table class='heal-table'>"
        "<thead><tr><th>Failed selector</th><th>Healed to</th><th>Reason</th><th>Confidence</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )

def _failure_analysis(r: TestResult) -> str:
    fa = r.failure_analysis
    if not fa or fa.get("category") == "none":
        return ""
    cat   = _e(FailureAnalyzer.category_label(fa.get("category", "unknown")))
    rc    = _e(fa.get("root_cause", ""))
    expl  = _e(fa.get("explanation", ""))
    fix   = _e(fa.get("suggested_fix", ""))
    conf  = float(fa.get("confidence", 0))
    meth  = _e(fa.get("method", "heuristic"))
    return (
        "<h3>🔍 Failure analysis <small style='font-weight:400;font-size:.8em;color:#888'>"
        f"({meth})</small></h3>"
        f"<table style='width:100%;border-collapse:collapse;font-size:.87rem'>"
        f"<tr><td style='padding:4px 8px;width:130px;color:#888;white-space:nowrap'>Category</td>"
        f"<td style='padding:4px 8px'><strong>{cat}</strong></td></tr>"
        f"<tr><td style='padding:4px 8px;color:#888'>Root cause</td>"
        f"<td style='padding:4px 8px'>{rc}</td></tr>"
        + (f"<tr><td style='padding:4px 8px;color:#888;vertical-align:top'>Explanation</td>"
           f"<td style='padding:4px 8px'>{expl}</td></tr>" if expl else "")
        + (f"<tr><td style='padding:4px 8px;color:#888;vertical-align:top'>Suggested fix</td>"
           f"<td style='padding:4px 8px;color:#137333'>{fix}</td></tr>" if fix else "")
        + f"<tr><td style='padding:4px 8px;color:#888'>Confidence</td>"
          f"<td style='padding:4px 8px'>{_conf_pill(conf)}</td></tr>"
        + "</table>"
    )


def _error_blocks(r: TestResult) -> str:
    out = ""
    if r.error:
        out += f"<div class='error-msg'>⛔ {_e(r.error)}</div>"
    if r.console_errors:
        joined = _e("\n".join(r.console_errors))
        out += (
            "<h3>🖥 Console errors</h3>"
            f"<pre class='diag'>{joined}</pre>"
        )
    if r.api_errors:
        joined = _e("\n".join(r.api_errors))
        out += (
            "<h3>🌐 Network errors</h3>"
            f"<pre class='diag'>{joined}</pre>"
        )
    return out

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def write_html_report(
    results: Iterable[TestResult],
    output_dir: str = "reports",
    suite_name: str = "",
    started_at: str = "",
) -> str:
    results: List[TestResult] = list(results)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    total   = len(results)
    passed  = sum(r.status == "PASS" for r in results)
    failed  = total - passed
    total_dur = sum(r.duration for r in results)
    rate    = (passed / total * 100) if total else 0
    ts      = started_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title   = _e(suite_name) if suite_name else "AI Test Report"

    # --- dashboard ---
    rate_bar = (
        f"<div class='rate-bar-wrap'><div class='rate-bar' style='width:{rate:.1f}%'></div></div>"
        f"<div class='rate-label'>{rate:.1f}% pass rate</div>"
    )
    dashboard = (
        "<div class='dashboard'>"
        f"<div class='stat total'><div class='value'>{total}</div><div class='label'>Total</div></div>"
        f"<div class='stat pass'><div class='value'>{passed}</div><div class='label'>Passed</div></div>"
        f"<div class='stat fail'><div class='value'>{failed}</div><div class='label'>Failed</div></div>"
        f"<div class='stat dur'><div class='value'>{total_dur:.1f}s</div><div class='label'>Duration</div></div>"
        "</div>"
        f"<div class='card' style='padding:14px 20px'>{rate_bar}</div>"
    )

    # --- test cards ---
    cards = []
    for r in results:
        status_cls = "pass" if r.status == "PASS" else "fail"
        badge_txt  = "✅ PASS" if r.status == "PASS" else "❌ FAIL"

        header = (
            "<div class='test-header'>"
            f"<span class='test-id'>{_e(r.id)}</span>"
            f"<span class='test-name'>{_e(r.name)}</span>"
            f"<span class='badge {status_cls}'>{badge_txt}</span>"
            f"<span class='dur-badge'>{r.duration:.2f}s</span>"
            "</div>"
        )

        val_section = (
            "<div class='section'>"
            "<h3>Validations</h3>"
            + _validation_list(r.validations)
            + "</div>"
        )

        fa_section = ""
        if r.failure_analysis and r.failure_analysis.get("category") != "none":
            fa_section = f"<div class='section'>{_failure_analysis(r)}</div>"

        heal_section = ""
        if r.healed_selectors:
            heal_section = f"<div class='section'>{_healing_table(r.healed_selectors)}</div>"

        screenshot_section = ""
        if r.screenshot:
            screenshot_section = f"<div class='section'>{_inline_screenshot(r.screenshot)}</div>"

        diag_section = ""
        diag_content = _error_blocks(r)
        if diag_content:
            diag_section = f"<div class='section'>{diag_content}</div>"

        cards.append(
            f"<div class='card test-card {status_cls}'>"
            f"{header}{val_section}{fa_section}{heal_section}{screenshot_section}{diag_section}"
            "</div>"
        )

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>{_CSS}</style>
</head>
<body>
<h1>{title}</h1>
<p class="subtitle">Generated {_e(ts)}</p>
{dashboard}
{''.join(cards)}
</body>
</html>"""

    target = out / "test_report.html"
    target.write_text(page, encoding="utf-8")
    return str(target)
