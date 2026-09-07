"""Cloud/SaaS integration primitives.

This package deliberately sits beside the deterministic test engine. Cloud
transport concerns should depend on these contracts rather than modifying
Playwright execution internals.
"""

from .contracts import ExecutionRequest, ExecutionSpec, ExecutionStatus
from .engine import EngineAdapter, LocalEngineAdapter

__all__ = [
    "EngineAdapter",
    "ExecutionRequest",
    "ExecutionSpec",
    "ExecutionStatus",
    "LocalEngineAdapter",
]
