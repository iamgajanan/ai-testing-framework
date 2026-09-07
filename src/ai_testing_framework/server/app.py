from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from ..cloud.contracts import ExecutionSpec
from .auth import AuthenticatedUser, get_current_user
from .db import SupabaseDataClient, SupabaseDataError, get_data_client


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


class OrganizationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ProjectCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: UUID
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _data_error(exc: SupabaseDataError) -> HTTPException:
    if exc.status_code in {401, 403, 404, 409, 422}:
        return HTTPException(status_code=exc.status_code, detail=str(exc))
    return HTTPException(status_code=502, detail="Database request failed")


def create_app() -> FastAPI:
    app = FastAPI(title="AI Testing Platform API", version="0.1.0")

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", service="ai-testing-platform-api", version=app.version)

    @app.get("/ready", response_model=HealthResponse)
    def ready() -> HealthResponse:
        return HealthResponse(status="ready", service="ai-testing-platform-api", version=app.version)

    @app.get("/v1/me")
    def me(user: AuthenticatedUser = Depends(get_current_user)) -> dict[str, Any]:
        return {"id": user.id, "email": user.email}

    @app.get("/v1/organizations")
    async def list_organizations(
        db: SupabaseDataClient = Depends(get_data_client),
    ) -> list[dict[str, Any]]:
        try:
            return await db.select(
                "organizations",
                select="id,name,slug,created_by,created_at,updated_at",
                order="created_at.asc",
            )
        except SupabaseDataError as exc:
            raise _data_error(exc) from exc

    @app.post("/v1/organizations", status_code=status.HTTP_201_CREATED)
    async def create_organization(
        payload: OrganizationCreateRequest,
        user: AuthenticatedUser = Depends(get_current_user),
        db: SupabaseDataClient = Depends(get_data_client),
    ) -> dict[str, Any]:
        try:
            rows = await db.insert(
                "organizations",
                {"name": payload.name.strip(), "slug": payload.slug, "created_by": user.id},
            )
            return rows[0]
        except SupabaseDataError as exc:
            raise _data_error(exc) from exc

    @app.get("/v1/projects")
    async def list_projects(
        organization_id: UUID = Query(...),
        db: SupabaseDataClient = Depends(get_data_client),
    ) -> list[dict[str, Any]]:
        try:
            return await db.select(
                "projects",
                select="id,organization_id,name,slug,created_by,created_at,updated_at",
                filters={"organization_id": f"eq.{organization_id}"},
                order="created_at.asc",
            )
        except SupabaseDataError as exc:
            raise _data_error(exc) from exc

    @app.post("/v1/projects", status_code=status.HTTP_201_CREATED)
    async def create_project(
        payload: ProjectCreateRequest,
        user: AuthenticatedUser = Depends(get_current_user),
        db: SupabaseDataClient = Depends(get_data_client),
    ) -> dict[str, Any]:
        try:
            rows = await db.insert(
                "projects",
                {
                    "organization_id": str(payload.organization_id),
                    "name": payload.name.strip(),
                    "slug": payload.slug,
                    "created_by": user.id,
                },
            )
            return rows[0]
        except SupabaseDataError as exc:
            raise _data_error(exc) from exc

    @app.post("/v1/executions", response_model=ExecutionAcceptedResponse, status_code=202)
    def create_execution(
        payload: ExecutionRequestModel,
        user: AuthenticatedUser = Depends(get_current_user),
    ) -> ExecutionAcceptedResponse:
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
            message=f"Execution contract accepted for authenticated user {user.id}; dispatcher is not configured yet.",
        )

    return app


app = create_app()
