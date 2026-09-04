from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


DEFAULT_CONFIG = {
    "browser": "chromium",
    "headless": True,
    "timeout": 30000,
    "ai": {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0},
    "report": {"output_dir": "reports", "html": True, "json": True},
    "screenshots": {"on_failure": True},
}


def load_config(path: str | None = None) -> Dict[str, Any]:
    config = DEFAULT_CONFIG.copy()
    if path and Path(path).exists():
        user = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        config = _deep_merge(config, user)
    return config


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
