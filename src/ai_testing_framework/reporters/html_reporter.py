"""Self-contained HTML reporting for test results."""
from __future__ import annotations

import base64
import html as _html
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from ..ai.failure_analyzer import FailureAnalyzer
from ..core.models import TestResult
from .history import flaky_tests


_CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,-apple-system,sans-serif;font-size:14px;background:#f0f2f5;color:#1a1a2e;padding:32px 20px}
h1{font-size:1.6rem;margin-bottom:4px}.subtitle{color:#666;font-size:.85rem;margin-bottom:28px}
h2{font-size:1.1rem;margin-bottom:12px}h3{font-size:.9rem;color:#555;margin:16px 0 8px;text-transform:uppercase;letter-spacing:.04em}
.card,.stat{background:#fff;border-radius:12px;box-shadow:0 1px 4px rgba(0,0,0,.08)}
.card{padding:20px 24px;margin-bottom:16px}.dashboard{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px}
.stat{padding:16px 24px;flex:1;min-width:140px;text-align:center}.stat .value{font-size:2rem;font-weight:700}.stat .label{font-size:.75rem;color:#888;text-transform:uppercase}
.stat.pass .value{color:#137333}.stat.fail .value{color:#b3261e}.stat.total .value{color:#1a73e8}.stat.dur .value{font-size:1.5rem;color:#555}
.rate-bar-wrap{background:#e8eaed;border-radius:999px;height:8px;margin:8px 0 4px;overflow:hidden}.rate-bar{height:100%;background:#137333;border-radius:999px}.rate-label{font-size:.82rem;color:#555;text-align:right}
.test-card{border-left:4px solid #e0e0e0}.test-card.pass{border-left-color:#34a853}.test-card.fail{border-left-color:#ea4335}
.test-header{display:flex;align-items:center;gap:12px;margin-bottom:12px}.test-id,.mono{font-family:monospace;font-size:.82rem;background:#f1f3f4;padding:2px 7px;border-radius:5px}.test-name{flex:1;font-weight:600}.badge{padding:3px 12px;border-radius:999px;font-weight:700;font-size:.8rem}.badge.pass{background:#e6f4ea;color:#137333}.badge.fail{background:#fce8e6;color:#b3261e}.dur-badge{font-size:.78rem;color:#888}
.section{margin-top:14px;padding-top:14px;border-top:1px solid #f0f0f0}.trace{width:100%;border-collapse:collapse;font-size:.84rem}.trace th{background:#f8f9fa;text-align:left}.trace th,.trace td{padding:7px 8px;border-bottom:1px solid #eee;vertical-align:top}.trace .fail{color:#b3261e;font-weight:600}.trace .pass{color:#137333;font-weight:600}
.val-list{list-style:none}.val-list li{display:flex;gap:8px;padding:5px 0;border-bottom:1px solid #f8f8f8}.val-type{font-family:monospace;font-size:.8rem;background:#f1f3f4;padding:1px 6px;border-radius:4px}.val-reason{flex:1;color:#444}.conf{font-size:.78rem;color:#777;white-space:nowrap}
.heal-table,.flaky-table{width:100%;border-collapse:collapse;font-size:.84rem}.heal-table th,.flaky-table th{background:#fff8e1}.heal-table th,.heal-table td,.flaky-table th,.flaky-table td{padding:7px 9px;border-bottom:1px solid #eee;text-align:left}
.error-msg{background:#fce8e6;border-left:3px solid #ea4335;padding:8px 12px;color:#b3261e}.diag{background:#f8f9fa;border:1px solid #e0e0e0;border-radius:8px;padding:12px;white-space:pre-wrap;word-break:break-word;max-height:300px;overflow:auto}
.screenshot img{max-width:100%;border:1px solid #ddd;border-radius:8px;margin-top:8px}.screenshot summary{cursor:pointer;color:#1a73e8}
"""


def _e(value) -> str:
    return _html.escape(str(value))


def _conf(value) -> str:
    try:
        return f"{float(value):.0%}"
    except (TypeError, ValueError):
        return ""


def _inline_screenshot(path: str) -> str:
    try:
        data = base64.b64encode(Path(path).read_bytes()).decode()
        return f"<details class='screenshot'><summary>📷 Failure screenshot</summary><img src='data:image/png;base64,{data}' alt='failure screenshot'></details>"
    except Exception:
        return f"<small>Screenshot: {_e(path)}</small>"


def _steps(result: TestResult) -> str:
    if not result.steps:
        return "<p style='color:#888'>No steps recorded.</p>"
    rows = []
    for i, step in enumerate(result.steps, 1):
        value = "" if step.value is None else _e(step.value)
        output = "" if step.result is None else _e(step.result)
        error = f"<br><span class='fail'>{_e(step.error)}</span>" if step.error else ""
        rows.append(
            f"<tr><td>{i}</td><td>{_e(step.action)}</td><td>{_e(step.selector or '')}</td>"
            f"<td>{value}</td><td class='{step.status.lower()}'>{_e(step.status)}</td>"
            f"<td>{step.duration:.3f}s</td><td>{output}{error}</td></tr>"
        )
    return "<table class='trace'><thead><tr><th>#</th><th>Action</th><th>Selector</th><th>Value</th><th>Status</th><th>Time</th><th>Result/Error</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def _validations(validations) -> str:
    if not validations:
        return "<p style='color:#888'>No validations recorded.</p>"
    rows = []
    for v in validations:
        actual = f"<br><small>Actual: {_e(str(v.actual)[:300])}</small>" if v.actual is not None and not v.passed else ""
        confidence = f"<span class='conf'>{_conf(v.confidence)}</span>" if v.confidence is not None else ""
        rows.append(f"<li><span>{'✅' if v.passed else '❌'}</span><span class='val-type'>{_e(v.type)}</span><span class='val-reason'>{_e(v.reason)}{actual}</span>{confidence}</li>")
    return "<ul class='val-list'>" + "".join(rows) + "</ul>"


def _healing(healed: list) -> str:
    if not healed:
        return ""
    rows = [f"<tr><td>{_e(h.get('failed_selector',''))}</td><td>{_e(h.get('healed_selector',''))}</td><td>{_e(h.get('reason',''))}</td><td>{_conf(h.get('confidence',0))}</td></tr>" for h in healed]
    return "<h3>⚕️ Self-healed selectors</h3><table class='heal-table'><thead><tr><th>Failed</th><th>Healed to</th><th>Reason</th><th>Confidence</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def _failure(r: TestResult) -> str:
    fa = r.failure_analysis
    if not fa or fa.get('category') == 'none':
        return ""
    return (f"<h3>🔍 Failure analysis <small>({_e(fa.get('method','heuristic'))})</small></h3>"
            f"<p><strong>{_e(FailureAnalyzer.category_label(fa.get('category','unknown')))}</strong> — {_e(fa.get('root_cause',''))}</p>"
            f"<p>{_e(fa.get('explanation',''))}</p><p><strong>Suggested fix:</strong> {_e(fa.get('suggested_fix',''))}</p>"
            f"<p>Confidence: {_conf(fa.get('confidence',0))}</p>")


def _errors(r: TestResult) -> str:
    out = f"<div class='error-msg'>⛔ {_e(r.error)}</div>" if r.error else ""
    if r.console_errors:
        out += f"<h3>🖥 Console errors</h3><pre class='diag'>{_e(chr(10).join(r.console_errors))}</pre>"
    if r.api_errors:
        out += f"<h3>🌐 Network errors</h3><pre class='diag'>{_e(chr(10).join(r.api_errors))}</pre>"
    return out


def _flaky_section(output_dir: str) -> str:
    items = flaky_tests(output_dir)
    if not items:
        return ""
    rows = [f"<tr><td>{_e(x['id'])}</td><td>{_e(x['name'])}</td><td>{x['total_runs']}</td><td>{x['pass']}</td><td>{x['fail']}</td><td>{x['flaky_rate']:.1f}%</td></tr>" for x in items]
    return "<div class='card'><h2>⚠️ Flaky tests</h2><table class='flaky-table'><thead><tr><th>ID</th><th>Name</th><th>Runs</th><th>Pass</th><th>Fail</th><th>Flaky rate</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"


def write_html_report(results: Iterable[TestResult], output_dir: str = "reports", suite_name: str = "", started_at: str = "") -> str:
    results: List[TestResult] = list(results)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    total = len(results)
    passed = sum(r.status == 'PASS' for r in results)
    failed = total - passed
    duration = sum(r.duration for r in results)
    rate = passed / total * 100 if total else 0
    title = _e(suite_name or 'AI Test Report')
    ts = _e(started_at or datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    cards = []
    for r in results:
        cls = 'pass' if r.status == 'PASS' else 'fail'
        cards.append(
            f"<div class='card test-card {cls}'><div class='test-header'><span class='test-id'>{_e(r.id)}</span><span class='test-name'>{_e(r.name)}</span><span class='badge {cls}'>{'✅ PASS' if cls == 'pass' else '❌ FAIL'}</span><span class='dur-badge'>{r.duration:.2f}s</span></div>"
            f"<div class='section'><h3>Step execution trace</h3>{_steps(r)}</div>"
            f"<div class='section'><h3>Validations</h3>{_validations(r.validations)}</div>"
            f"{('<div class=\'section\'>' + _failure(r) + '</div>') if r.failure_analysis and r.failure_analysis.get('category') != 'none' else ''}"
            f"{('<div class=\'section\'>' + _healing(r.healed_selectors) + '</div>') if r.healed_selectors else ''}"
            f"{('<div class=\'section\'>' + _inline_screenshot(r.screenshot) + '</div>') if r.screenshot else ''}"
            f"{('<div class=\'section\'>' + _errors(r) + '</div>') if (r.error or r.console_errors or r.api_errors) else ''}</div>"
        )

    html = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{title}</title><style>{_CSS}</style></head><body>
<h1>{title}</h1><p class='subtitle'>Generated {ts}</p>
<div class='dashboard'><div class='stat total'><div class='value'>{total}</div><div class='label'>Total</div></div><div class='stat pass'><div class='value'>{passed}</div><div class='label'>Passed</div></div><div class='stat fail'><div class='value'>{failed}</div><div class='label'>Failed</div></div><div class='stat dur'><div class='value'>{duration:.1f}s</div><div class='label'>Duration</div></div></div>
<div class='card'><div class='rate-bar-wrap'><div class='rate-bar' style='width:{rate:.1f}%'></div></div><div class='rate-label'>{rate:.1f}% pass rate</div></div>
{_flaky_section(output_dir)}{''.join(cards)}
</body></html>"""
    target = out / 'test_report.html'
    target.write_text(html, encoding='utf-8')
    return str(target)
