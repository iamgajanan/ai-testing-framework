"""PDF reporter for the Universal AI Testing Framework — Phase 5.

Uses reportlab (pure Python, no headless browser). Produces a readable
test report with: summary table, pass rate, per-test sections with
validation results, self-healing events, and error details.

Requires: reportlab>=4.0
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from ..core.models import TestResult

# Colour constants (RGB 0-1)
_GREEN  = (0.075, 0.450, 0.200)
_RED    = (0.702, 0.149, 0.118)
_ORANGE = (0.486, 0.341, 0.000)
_BLUE   = (0.102, 0.451, 0.914)
_GREY   = (0.45,  0.45,  0.45)
_LGREY  = (0.95,  0.95,  0.95)
_WHITE  = (1.0,   1.0,   1.0)
_BLACK  = (0.1,   0.1,   0.1)


def write_pdf_report(
    results: Iterable[TestResult],
    output_dir: str = "reports",
    suite_name: str = "",
    started_at: str = "",
) -> str:
    """Write a PDF report and return the output file path."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
        )
    except ImportError as exc:
        raise ImportError(
            "PDF reporting requires reportlab: pip install 'reportlab>=4.0'"
        ) from exc

    results: List[TestResult] = list(results)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / "test_report.pdf"

    total    = len(results)
    passed   = sum(r.status == "PASS" for r in results)
    failed   = total - passed
    dur      = sum(r.duration for r in results)
    rate     = (passed / total * 100) if total else 0
    ts       = started_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title    = suite_name or "AI Test Report"

    doc = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=title,
    )

    styles = getSampleStyleSheet()
    W = A4[0] - 40 * mm  # usable width

    def _s(name, **kw):
        base = styles[name]
        return ParagraphStyle(name + "_custom", parent=base, **kw)

    S = {
        "h1":      _s("Title",    fontSize=18, textColor=colors.HexColor("#1a1a2e"), spaceAfter=4),
        "sub":     _s("Normal",   fontSize=9,  textColor=colors.grey, spaceAfter=16),
        "h2":      _s("Heading2", fontSize=13, textColor=colors.HexColor("#1a1a2e"), spaceBefore=14, spaceAfter=6),
        "h3":      _s("Heading3", fontSize=10, textColor=colors.HexColor("#444444"), spaceBefore=8, spaceAfter=4),
        "body":    _s("Normal",   fontSize=9,  leading=13),
        "mono":    _s("Code",     fontSize=8,  fontName="Courier", leading=11, backColor=colors.HexColor("#f1f3f4")),
        "pass":    _s("Normal",   fontSize=9,  textColor=colors.HexColor("#137333")),
        "fail":    _s("Normal",   fontSize=9,  textColor=colors.HexColor("#b3261e")),
        "error":   _s("Normal",   fontSize=9,  textColor=colors.HexColor("#b3261e"), backColor=colors.HexColor("#fce8e6")),
    }

    def P(text, style="body"):
        return Paragraph(str(text), S[style])

    def HR():
        return HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e0e0e0"), spaceAfter=6, spaceBefore=6)

    def _table(data, col_widths, style_cmds=None):
        t = Table(data, colWidths=col_widths)
        base = [
            ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, -1), 8),
            ("BACKGROUND",  (0, 0), (-1, 0),  colors.HexColor("#f0f2f5")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
            ("GRID",        (0, 0), (-1, -1), 0.4, colors.HexColor("#e0e0e0")),
            ("VALIGN",      (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",  (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",(0,0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",(0, 0), (-1, -1), 6),
        ]
        t.setStyle(TableStyle(base + (style_cmds or [])))
        return t

    story = []

    # ------------------------------------------------------------------
    # Cover / header
    # ------------------------------------------------------------------
    story += [
        P(title, "h1"),
        P(f"Generated {ts}  ·  {total} test(s)  ·  {dur:.1f}s total", "sub"),
        HR(),
    ]

    # Summary table
    summary_data = [
        ["Total", "Passed", "Failed", "Pass rate", "Duration"],
        [str(total), str(passed), str(failed), f"{rate:.1f}%", f"{dur:.2f}s"],
    ]
    story.append(
        _table(
            summary_data,
            [W * 0.15, W * 0.2, W * 0.2, W * 0.25, W * 0.2],
            [
                ("TEXTCOLOR", (1, 1), (1, 1), colors.HexColor("#137333")),
                ("TEXTCOLOR", (2, 1), (2, 1), colors.HexColor("#b3261e") if failed else colors.HexColor("#137333")),
                ("FONTNAME",  (0, 1), (-1, 1), "Helvetica-Bold"),
            ],
        )
    )
    story.append(Spacer(1, 12))

    # ------------------------------------------------------------------
    # Per-test sections
    # ------------------------------------------------------------------
    for r in results:
        status_color = colors.HexColor("#137333") if r.status == "PASS" else colors.HexColor("#b3261e")
        status_label = "✓ PASS" if r.status == "PASS" else "✗ FAIL"

        story.append(HR())
        story.append(
            _table(
                [[f"{r.id}  –  {r.name}", status_label, f"{r.duration:.2f}s"]],
                [W * 0.65, W * 0.20, W * 0.15],
                [
                    ("FONTNAME",  (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE",  (0, 0), (-1, 0), 10),
                    ("TEXTCOLOR", (1, 0), (1, 0), status_color),
                    ("BACKGROUND",(0, 0), (-1, 0), colors.HexColor("#f8f9fa")),
                ],
            )
        )
        story.append(Spacer(1, 6))

        # Error
        if r.error:
            story.append(P(f"Error: {r.error}", "error"))
            story.append(Spacer(1, 4))

        # Validations
        if r.validations:
            story.append(P("Validations", "h3"))
            val_data = [["Type", "Result", "Reason", "Confidence"]]
            for v in r.validations:
                icon = "✓" if v.passed else "✗"
                conf = f"{v.confidence:.0%}" if v.confidence is not None else "—"
                val_data.append([
                    v.type,
                    icon,
                    str(v.reason)[:120],
                    conf,
                ])
            story.append(
                _table(
                    val_data,
                    [W * 0.22, W * 0.08, W * 0.55, W * 0.15],
                    [
                        ("TEXTCOLOR", (1, 1), (1, -1), colors.HexColor("#137333")),
                    ],
                )
            )
            story.append(Spacer(1, 6))

        # Self-healing
        if r.healed_selectors:
            story.append(P("Self-healed selectors", "h3"))
            heal_data = [["Failed selector", "Healed to", "Reason", "Confidence"]]
            for h in r.healed_selectors:
                conf = float(h.get("confidence", 0))
                heal_data.append([
                    h.get("failed_selector", ""),
                    h.get("healed_selector", ""),
                    str(h.get("reason", ""))[:80],
                    f"{conf:.0%}",
                ])
            story.append(
                _table(
                    heal_data,
                    [W * 0.22, W * 0.22, W * 0.41, W * 0.15],
                    [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fff8e1"))],
                )
            )
            story.append(Spacer(1, 6))

        # Console / network errors
        if r.console_errors:
            story.append(P("Console errors", "h3"))
            story.append(P("\n".join(r.console_errors[:10]), "mono"))
            story.append(Spacer(1, 4))
        if r.api_errors:
            story.append(P("Network errors", "h3"))
            story.append(P("\n".join(r.api_errors[:10]), "mono"))
            story.append(Spacer(1, 4))

    doc.build(story)
    return str(target)
