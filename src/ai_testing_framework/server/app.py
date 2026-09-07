from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

from ..cloud.contracts import ExecutionSpec


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ExecutionSpecRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suite_path: str = Field(min_length=1)
    base_url: str = ""
    browser: str = Field(default="chromium", pattern="^(chromium|firefox|webkit)$")
    test_id: str | None = None
    output_dir: str = "reports"
    formats: list[str] = Field(default_factory=lambda: ["html", "json"], min_length=1)
    workers: int = Field(default=1, ge=1, le=64)
    config: str | dict[str, Any] | None = None
    ai_provider: str | None = None


class ExecutionRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    requested_by: str | None = None
    spec: ExecutionSpecRequest
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionAcceptedResponse(BaseModel):
    status: str
    message: str


def create_app() -> FastAPI:
    app = FastAPI(title="AI Testing Platform API", version="0.1.0")

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", service="ai-testing-platform-api", version=app.version)

    @app.get("/ready", response_model=HealthResponse)
    def ready() -> HealthResponse:
        # Dependency checks will be added when PostgreSQL/queue are introduced.
        return HealthResponse(status="ready", service="ai-testing-platform-api", version=app.version)

    @app.post("/v1/executions", response_model=ExecutionAcceptedResponse, status_code=202)
    def create_execution(payload: ExecutionRequestModel) -> ExecutionAcceptedResponse:
        # Deliberately do not execute synchronously. Phase 1A establishes the
        # contract; queue/worker persistence is the next implementation step.
        ExecutionSpec(
            suite_path=payload.spec.suite_path,
            base_url=payload.spec.base_url,
            browser=payload.spec.browser,
            test_id=payload.spec.test_id,
            output_dir=payload.spec.output_dir,
            formats=tuple(payload.spec.formats),
            workers=payload.spec.workers,
            config=payload.spec.config,
            ai_provider=payload.spec.ai_provider,
        )
        return ExecutionAcceptedResponse(
            status="accepted",
            message="Execution contract accepted; cloud dispatcher is not configured yet.",
        )

    return app


app = create_app()
