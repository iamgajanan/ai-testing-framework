from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ExecutionStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class ExecutionSpec:
    """Engine-neutral description of one requested test execution."""

    suite_path: str
    base_url: str = ""
    browser: str = "chromium"
    test_id: str | None = None
    output_dir: str = "reports"
    formats: tuple[str, ...] = ("html", "json")
    workers: int = 1
    config: str | dict[str, Any] | None = None
    ai_provider: str | None = None


@dataclass(frozen=True)
class ExecutionRequest:
    """SaaS-facing execution envelope.

    ``organization_id`` and ``project_id`` are opaque identifiers on purpose;
    persistence/authentication will own their concrete representation later.
    """

    organization_id: str
    project_id: str
    spec: ExecutionSpec
    requested_by: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
