"""Test history tracker — Phase 5.

Appends each run to history.json in the output directory. Each entry
records the timestamp, pass/fail counts, pass rate, duration, and
per-test status. This enables trend detection and flaky-test signals
without requiring a database.

Usage (called automatically by TestRunner):
    from .reporters.history import append_history
    append_history(results, output_dir, suite_name)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

from ..core.models import TestResult

# Maximum number of run entries to keep in history.json (rolling window)
_MAX_ENTRIES = 100


def append_history(
    results: Iterable[TestResult],
    output_dir: str = "reports",
    suite_name: str = "",
    started_at: str = "",
) -> str:
    """Append this run to history.json and return the file path."""
    results: List[TestResult] = list(results)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    history_file = out / "history.json"

    # Load existing history
    existing: list = []
    if history_file.exists():
        try:
            existing = json.loads(history_file.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = []
        except (json.JSONDecodeError, OSError):
            existing = []

    total    = len(results)
    passed   = sum(r.status == "PASS" for r in results)
    failed   = total - passed
    duration = round(sum(r.duration for r in results), 3)
    ts       = started_at or datetime.now(timezone.utc).isoformat()

    entry = {
        "run_at":     ts,
        "suite_name": suite_name or "AI Test Suite",
        "total":      total,
        "passed":     passed,
        "failed":     failed,
        "pass_rate":  round((passed / total * 100) if total else 0, 1),
        "duration":   duration,
        "tests": [
            {
                "id":       r.id,
                "name":     r.name,
                "status":   r.status,
                "duration": round(r.duration, 3),
                "healed":   len(r.healed_selectors),
                "error":    r.error if r.status != "PASS" else "",
            }
            for r in results
        ],
    }

    existing.append(entry)
    # Keep only the last _MAX_ENTRIES runs
    if len(existing) > _MAX_ENTRIES:
        existing = existing[-_MAX_ENTRIES:]

    history_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(history_file)


def flaky_tests(output_dir: str = "reports", min_runs: int = 3) -> list[dict]:
    """Return tests that have both PASS and FAIL in recent history.

    A test is 'flaky' when it has appeared at least ``min_runs`` times
    and has at least one PASS and one FAIL in the recorded history.
    """
    history_file = Path(output_dir) / "history.json"
    if not history_file.exists():
        return []
    try:
        runs: list = json.loads(history_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    # Aggregate per test-id
    stats: dict[str, dict] = {}
    for run in runs:
        for t in run.get("tests", []):
            tid = t.get("id", "")
            if tid not in stats:
                stats[tid] = {"id": tid, "name": t.get("name", ""), "pass": 0, "fail": 0}
            if t.get("status") == "PASS":
                stats[tid]["pass"] += 1
            else:
                stats[tid]["fail"] += 1

    flaky = []
    for s in stats.values():
        total = s["pass"] + s["fail"]
        if total >= min_runs and s["pass"] > 0 and s["fail"] > 0:
            s["flaky_rate"] = round(s["fail"] / total * 100, 1)
            s["total_runs"] = total
            flaky.append(s)

    flaky.sort(key=lambda x: x["flaky_rate"], reverse=True)
    return flaky
