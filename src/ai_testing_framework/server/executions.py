from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ..cloud.contracts import ExecutionSpec


@dataclass(frozen=True)
class ExecutionRecord:
    id: UUID
    organization_id: UUID
    project_id: UUID
    requested_by: UUID
    status: str
    spec: ExecutionSpec
    metadata: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "ExecutionRecord":
        config = row.get("config")
        return cls(
            id=UUID(str(row["id"])),
            organization_id=UUID(str(row["organization_id"])),
            project_id=UUID(str(row["project_id"])),
            requested_by=UUID(str(row["requested_by"])),
            status=str(row["status"]),
            spec=ExecutionSpec(
                suite_path=row["suite_path"],
                base_url=row.get("base_url", ""),
                browser=row.get("browser", "chromium"),
                test_id=row.get("test_id"),
                output_dir=row.get("output_dir", "reports"),
                formats=tuple(row.get("formats") or ["html", "json"]),
                workers=int(row.get("workers", 1)),
                config=config,
                ai_provider=row.get("ai_provider"),
            ),
            metadata=row.get("metadata") or {},
            result=row.get("result"),
            error=row.get("error"),
        )

    def to_response(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "project_id": str(self.project_id),
            "requested_by": str(self.requested_by),
            "status": self.status,
            "suite_path": self.spec.suite_path,
            "base_url": self.spec.base_url,
            "browser": self.spec.browser,
            "test_id": self.spec.test_id,
            "output_dir": self.spec.output_dir,
            "formats": list(self.spec.formats),
            "workers": self.spec.workers,
            "config": self.spec.config,
            "ai_provider": self.spec.ai_provider,
            "metadata": self.metadata,
            "result": self.result,
            "error": self.error,
        }
