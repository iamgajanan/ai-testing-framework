from __future__ import annotations

from pathlib import Path
from typing import Any


def compare_screenshots(actual: str, baseline: str, threshold: float = 0.0) -> tuple[bool, dict[str, Any]]:
    """Compare two screenshots and return pass plus diff metrics."""
    try:
        from PIL import Image, ImageChops
    except ImportError as exc:
        raise RuntimeError("Visual regression requires Pillow") from exc
    a = Image.open(actual).convert("RGBA")
    b = Image.open(baseline).convert("RGBA")
    if a.size != b.size:
        return False, {"reason": "image dimensions differ", "actual_size": a.size, "baseline_size": b.size, "diff_ratio": 1.0}
    diff = ImageChops.difference(a, b)
    bbox = diff.getbbox()
    if bbox is None:
        ratio = 0.0
    else:
        histogram = diff.convert("L").histogram()
        changed = sum(histogram[1:])
        total = a.size[0] * a.size[1] * 255
        ratio = changed / total if total else 0.0
    passed = ratio <= max(0.0, float(threshold))
    return passed, {"diff_ratio": ratio, "threshold": float(threshold), "actual_size": a.size, "baseline": str(Path(baseline))}
