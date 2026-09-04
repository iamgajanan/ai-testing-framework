from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from ..core.models import TestResult


def write_json_report(results: Iterable[TestResult], output_dir: str = "reports") -> str:
    results = list(results)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    total = len(results)
    payload = {
        "total_tests": total,
        "passed": sum(r.status == "PASS" for r in results),
        "failed": sum(r.status != "PASS" for r in results),
        "results": [r.to_dict() for r in results],
    }
    target = out / "test_report.json"
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(target)
