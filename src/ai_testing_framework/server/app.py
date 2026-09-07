from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from ..cloud.contracts import ExecutionSpec
from .auth import AuthenticatedUser, get_current_user
from .db import SupabaseDataClient, SupabaseDataError, get_data_client
from .executions import ExecutionRecord


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
    organization_id: UUID
    project_id: UUID
    requested_by: str | None = None
    spec: ExecutionSpecRequest
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionResponse(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    requested_by: UUID
    status: str
    suite_path: str
    base_url: str
    browser: str
    test_id: str | None
    output_dir: str
    formats: list[str]
    workers: int
    config: str | dict[str, Any] | None
    ai_provider: str | None
    metadata: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None


class ExecutionAcceptedResponse(ExecutionResponse):
    pass


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


def _execution_select() -> str:
    return "id,organization_id,project_id,requested_by,status,suite_path,base_url,browser,test_id,output_dir,formats,workers,config,ai_provider,metadata,result,error"


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
    async def list_organizations(db: SupabaseDataClient = Depends(get_data_client)) -> list[dict[str, Any]]:
        try:
            return await db.select("organizations", select="id,name,slug,created_by,created_at,updated_at", order="created_at.asc")
        except SupabaseDataError as exc:
            raise _data_error(exc) from exc

    @app.post("/v1/organizations", status_code=status.HTTP_201_CREATED)
    async def create_organization(payload: OrganizationCreateRequest, user: AuthenticatedUser = Depends(get_current_user), db: SupabaseDataClient = Depends(get_data_client)) -> dict[str, Any]:
        try:
            rows = await db.insert("organizations", {"name": payload.name.strip(), "slug": payload.slug, "created_by": user.id})
            return rows[0]
        except SupabaseDataError as exc:
            raise _data_error(exc) from exc

    @app.get("/v1/projects")
    async def list_projects(organization_id: UUID = Query(...), db: SupabaseDataClient = Depends(get_data_client)) -> list[dict[str, Any]]:
        try:
            return await db.select("projects", select="id,organization_id,name,slug,created_by,created_at,updated_at", filters={"organization_id": f"eq.{organization_id}"}, order="created_at.asc")
        except SupabaseDataError as exc:
            raise _data_error(exc) from exc

    @app.post("/v1/projects", status_code=status.HTTP_201_CREATED)
    async def create_project(payload: ProjectCreateRequest, user: AuthenticatedUser = Depends(get_current_user), db: SupabaseDataClient = Depends(get_data_client)) -> dict[str, Any]:
        try:
            rows = await db.insert("projects", {"organization_id": str(payload.organization_id), "name": payload.name.strip(), "slug": payload.slug, "created_by": user.id})
            return rows[0]
        except SupabaseDataError as exc:
            raise _data_error(exc) from exc

    @app.post("/v1/executions", response_model=ExecutionResponse, status_code=202)
    async def create_execution(payload: ExecutionRequestModel, user: AuthenticatedUser = Depends(get_current_user), db: SupabaseDataClient = Depends(get_data_client)) -> ExecutionResponse:
        if payload.requested_by and payload.requested_by != user.id:
            raise HTTPException(status_code=403, detail="requested_by must match the authenticated user")
        spec = ExecutionSpec(
            suite_path=payload.spec.suite_path, base_url=payload.spec.base_url, browser=payload.spec.browser,
            test_id=payload.spec.test_id, output_dir=payload.spec.output_dir, formats=tuple(payload.spec.formats),
            workers=payload.spec.workers, config=payload.spec.config, ai_provider=payload.spec.ai_provider,
        )
        row = {
            "organization_id": str(payload.organization_id), "project_id": str(payload.project_id), "requested_by": user.id,
            "status": "queued", "suite_path": spec.suite_path, "base_url": spec.base_url, "browser": spec.browser,
            "test_id": spec.test_id, "output_dir": spec.output_dir, "formats": list(spec.formats), "workers": spec.workers,
            "config": spec.config, "ai_provider": spec.ai_provider, "metadata": payload.metadata,
        }
        try:
            rows = await db.insert("executions", row)
            return ExecutionResponse.model_validate(ExecutionRecord.from_row(rows[0]).to_response())
        except SupabaseDataError as exc:
            raise _data_error(exc) from exc

    @app.get("/v1/executions", response_model=list[ExecutionResponse])
    async def list_executions(organization_id: UUID = Query(...), limit: int = Query(default=50, ge=1, le=100), db: SupabaseDataClient = Depends(get_data_client)) -> list[ExecutionResponse]:
        try:
            rows = await db.select("executions", select=_execution_select(), filters={"organization_id": f"eq.{organization_id}"}, order="created_at.desc", limit=limit)
            return [ExecutionResponse.model_validate(ExecutionRecord.from_row(row).to_response()) for row in rows]
        except SupabaseDataError as exc:
            raise _data_error(exc) from exc

    @app.get("/v1/executions/{execution_id}", response_model=ExecutionResponse)
    async def get_execution(execution_id: UUID, db: SupabaseDataClient = Depends(get_data_client)) -> ExecutionResponse:
        try:
            rows = await db.select("executions", select=_execution_select(), filters={"id": f"eq.{execution_id}"}, limit=1)
            if not rows:
                raise HTTPException(status_code=404, detail="Execution not found")
            return ExecutionResponse.model_validate(ExecutionRecord.from_row(rows[0]).to_response())
        except SupabaseDataError as exc:
            raise _data_error(exc) from exc

    return app


app = create_app()
