from __future__ import annotations
from pathlib import Path
from typing import Any, Dict
import yaml
DEFAULT_CONFIG={"browser":"chromium","headless":True,"timeout":30000,"ai":{"provider":"openai","model":"gpt-4o-mini","temperature":0},"report":{"output_dir":"reports","html":True,"json":True},"screenshots":{"on_failure":True},"parallel":{"workers":1},"artifacts":{"trace_on_failure":True,"video_on_failure":True},"visual":{"pixel_threshold":0.0}}
def load_config(path:str|None=None)->Dict[str,Any]:
    config=_deep_merge({},DEFAULT_CONFIG)
    if path and Path(path).exists(): config=_deep_merge(config,yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {})
    return config
def _deep_merge(base:Dict[str,Any],override:Dict[str,Any])->Dict[str,Any]:
    result=dict(base)
    for key,value in override.items(): result[key]=_deep_merge(result.get(key,{}),value) if isinstance(value,dict) and isinstance(result.get(key),dict) else value
    return result
