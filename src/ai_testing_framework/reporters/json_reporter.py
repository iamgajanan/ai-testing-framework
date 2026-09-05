"""JSON reporter for the Universal AI Testing Framework — Phase 5.

Produces test_report.json with full metadata (suite name, timestamps,
total duration) for machine consumption in CI pipelines.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

from ..core.models import TestResult


def write_json_report(
    results: Iterable[TestResult],
    output_dir: str = "reports",
    suite_name: str = "",
    started_at: str = "",
) -> str:
    results: List[TestResult] = list(results)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    total     = len(results)
    passed    = sum(r.status == "PASS" for r in results)
    failed    = total - passed
    total_dur = round(sum(r.duration for r in results), 3)
    ts        = started_at or datetime.now(timezone.utc).isoformat()

    payload = {
        "suite_name":    suite_name or "AI Test Suite",
        "started_at":    ts,
        "total_tests":   total,
        "passed":        passed,
        "failed":        failed,
        "pass_rate":     round((passed / total * 100) if total else 0, 1),
        "total_duration": total_dur,
        "results":       [r.to_dict() for r in results],
    }

    target = out / "test_report.json"
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(target)
