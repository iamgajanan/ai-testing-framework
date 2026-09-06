from __future__ import annotations
from pathlib import Path
from typing import Any

def compare_screenshots(actual: str, baseline: str, threshold: float = 0.0) -> tuple[bool, dict[str, Any]]:
    try:
        from PIL import Image, ImageChops
    except ImportError as exc:
        raise RuntimeError("Visual regression requires Pillow") from exc
    a=Image.open(actual).convert("RGB"); b=Image.open(baseline).convert("RGB")
    if a.size!=b.size:return False,{"reason":"image dimensions differ","actual_size":a.size,"baseline_size":b.size,"diff_ratio":1.0}
    diff=ImageChops.difference(a,b);changed_pixels=sum(1 for pixel in diff.getdata() if pixel!=(0,0,0));total=a.size[0]*a.size[1];ratio=changed_pixels/total if total else 0.0;threshold=max(0.0,min(float(threshold),1.0));passed=ratio<=threshold
    return passed,{"diff_ratio":ratio,"threshold":threshold,"actual_size":a.size,"baseline":str(Path(baseline))}
