from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from ..cloud.contracts import ExecutionSpec
from .api_keys import create_project_api_key
from .auth import AuthenticatedUser, get_current_user
from .db import SupabaseDataClient, SupabaseDataError, SupabaseServiceClient, get_data_client
from .executions import ExecutionRecord
from .principal import ExecutionPrincipal, get_execution_principal
from .storage import SupabaseStorageClient


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
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class OrganizationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ProjectCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    organization_id: UUID
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class APIKeyCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)


class APIKeyResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    key_prefix: str
    scopes: list[str]
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    key: str | None = None


class ArtifactResponse(BaseModel):
    id: UUID
    execution_id: UUID
    name: str
    storage_path: str
    content_type: str
    size_bytes: int
    created_at: datetime


class ArtifactDownloadResponse(ArtifactResponse):
    signed_url: str
    expires_in: int


def _data_error(exc: SupabaseDataError) -> HTTPException:
    if exc.status_code in {400, 401, 403, 404, 409, 422}:
        return HTTPException(status_code=exc.status_code, detail=str(exc))
    return HTTPException(status_code=502, detail="Database request failed")


def _execution_select() -> str:
    return "id,organization_id,project_id,requested_by,status,suite_path,base_url,browser,test_id,output_dir,formats,workers,config,ai_provider,metadata,result,error,created_at,started_at,finished_at"


def _artifact_select() -> str:
    return "id,execution_id,name,storage_path,content_type,size_bytes,created_at"


def get_execution_db(principal: ExecutionPrincipal = Depends(get_execution_principal)) -> SupabaseDataClient | None:
    return SupabaseDataClient(principal.user) if principal.user else None


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

    @app.post("/v1/projects/{project_id}/api-keys", response_model=APIKeyResponse, status_code=201)
    async def create_api_key(project_id: UUID, payload: APIKeyCreateRequest, user: AuthenticatedUser = Depends(get_current_user), db: SupabaseDataClient = Depends(get_data_client)) -> APIKeyResponse:
        try:
            result = await create_project_api_key(project_id, payload.name, user, db)
            return APIKeyResponse.model_validate(result)
        except SupabaseDataError as exc:
            raise _data_error(exc) from exc

    @app.get("/v1/projects/{project_id}/api-keys", response_model=list[APIKeyResponse])
    async def list_api_keys(project_id: UUID, db: SupabaseDataClient = Depends(get_data_client)) -> list[APIKeyResponse]:
        try:
            rows = await db.select("project_api_keys", select="id,project_id,name,key_prefix,scopes,last_used_at,revoked_at,created_at", filters={"project_id": f"eq.{project_id}"}, order="created_at.desc")
            return [APIKeyResponse.model_validate(row) for row in rows]
        except SupabaseDataError as exc:
            raise _data_error(exc) from exc

    @app.post("/v1/projects/{project_id}/api-keys/{key_id}/revoke", response_model=APIKeyResponse)
    async def revoke_api_key(project_id: UUID, key_id: UUID, db: SupabaseDataClient = Depends(get_data_client)) -> APIKeyResponse:
        try:
            rows = await db.update("project_api_keys", {"id": f"eq.{key_id}", "project_id": f"eq.{project_id}"}, {"revoked_at": datetime.now(timezone.utc).isoformat()})
            if not rows:
                raise HTTPException(status_code=404, detail="API key not found")
            return APIKeyResponse.model_validate(rows[0])
        except SupabaseDataError as exc:
            raise _data_error(exc) from exc

    @app.post("/v1/executions", response_model=ExecutionResponse, status_code=202)
    async def create_execution(payload: ExecutionRequestModel, principal: ExecutionPrincipal = Depends(get_execution_principal), db: SupabaseDataClient | None = Depends(get_execution_db)) -> ExecutionResponse:
        principal.require_scope("executions:write")
        if principal.api_key and (str(payload.project_id) != principal.api_key.project_id or str(payload.organization_id) != principal.api_key.organization_id):
            raise HTTPException(status_code=403, detail="API key is scoped to a different project")
        if principal.user and payload.requested_by and payload.requested_by != principal.user.id:
            raise HTTPException(status_code=403, detail="requested_by must match the authenticated user")
        spec = ExecutionSpec(
            suite_path=payload.spec.suite_path, base_url=payload.spec.base_url, browser=payload.spec.browser,
            test_id=payload.spec.test_id, output_dir=payload.spec.output_dir, formats=tuple(payload.spec.formats),
            workers=payload.spec.workers, config=payload.spec.config, ai_provider=payload.spec.ai_provider,
        )
        row = {
            "organization_id": str(payload.organization_id), "project_id": str(payload.project_id), "requested_by": principal.requested_by,
            "status": "queued", "suite_path": spec.suite_path, "base_url": spec.base_url, "browser": spec.browser,
            "test_id": spec.test_id, "output_dir": spec.output_dir, "formats": list(spec.formats), "workers": spec.workers,
            "config": spec.config, "ai_provider": spec.ai_provider, "metadata": payload.metadata,
        }
        try:
            if principal.api_key:
                rows = await SupabaseServiceClient().insert("executions", row)
            else:
                assert db is not None
                rows = await db.insert("executions", row)
            return ExecutionResponse.model_validate(ExecutionRecord.from_row(rows[0]).to_response())
        except SupabaseDataError as exc:
            raise _data_error(exc) from exc

    @app.get("/v1/executions", response_model=list[ExecutionResponse])
    async def list_executions(organization_id: UUID = Query(...), limit: int = Query(default=50, ge=1, le=100), principal: ExecutionPrincipal = Depends(get_execution_principal), db: SupabaseDataClient | None = Depends(get_execution_db)) -> list[ExecutionResponse]:
        principal.require_scope("executions:read")
        if principal.api_key and str(organization_id) != principal.api_key.organization_id:
            raise HTTPException(status_code=403, detail="API key is scoped to a different organization")
        filters = {"organization_id": f"eq.{organization_id}"}
        if principal.api_key:
            filters["project_id"] = f"eq.{principal.api_key.project_id}"
        try:
            if principal.api_key:
                rows = await SupabaseServiceClient().select("executions", select=_execution_select(), filters=filters, order="created_at.desc", limit=limit)
            else:
                assert db is not None
                rows = await db.select("executions", select=_execution_select(), filters=filters, order="created_at.desc", limit=limit)
            return [ExecutionResponse.model_validate(ExecutionRecord.from_row(row).to_response()) for row in rows]
        except SupabaseDataError as exc:
            raise _data_error(exc) from exc

    @app.get("/v1/executions/{execution_id}/artifacts", response_model=list[ArtifactResponse])
    async def list_artifacts(execution_id: UUID, principal: ExecutionPrincipal = Depends(get_execution_principal), db: SupabaseDataClient | None = Depends(get_execution_db)) -> list[ArtifactResponse]:
        principal.require_scope("artifacts:read")
        filters = {"execution_id": f"eq.{execution_id}"}
        if principal.api_key:
            filters["project_id"] = f"eq.{principal.api_key.project_id}"
        try:
            if principal.api_key:
                rows = await SupabaseServiceClient().select("execution_artifacts", select=_artifact_select(), filters=filters, order="created_at.asc")
            else:
                assert db is not None
                rows = await db.select("execution_artifacts", select=_artifact_select(), filters=filters, order="created_at.asc")
            return [ArtifactResponse.model_validate(row) for row in rows]
        except SupabaseDataError as exc:
            raise _data_error(exc) from exc

    @app.get("/v1/executions/{execution_id}/artifacts/{artifact_id}", response_model=ArtifactDownloadResponse)
    async def get_artifact(execution_id: UUID, artifact_id: UUID, expires_in: int = Query(default=3600, ge=60, le=86400), principal: ExecutionPrincipal = Depends(get_execution_principal), db: SupabaseDataClient | None = Depends(get_execution_db)) -> ArtifactDownloadResponse:
        principal.require_scope("artifacts:read")
        filters = {"id": f"eq.{artifact_id}", "execution_id": f"eq.{execution_id}"}
        if principal.api_key:
            filters["project_id"] = f"eq.{principal.api_key.project_id}"
        try:
            if principal.api_key:
                rows = await SupabaseServiceClient().select("execution_artifacts", select=_artifact_select(), filters=filters, limit=1)
            else:
                assert db is not None
                rows = await db.select("execution_artifacts", select=_artifact_select(), filters=filters, limit=1)
            if not rows:
                raise HTTPException(status_code=404, detail="Artifact not found")
            signed_url = await SupabaseStorageClient().create_signed_url(rows[0]["storage_path"], expires_in)
            return ArtifactDownloadResponse.model_validate({**rows[0], "signed_url": signed_url, "expires_in": expires_in})
        except SupabaseDataError as exc:
            raise _data_error(exc) from exc

    @app.get("/v1/executions/{execution_id}", response_model=ExecutionResponse)
    async def get_execution(execution_id: UUID, principal: ExecutionPrincipal = Depends(get_execution_principal), db: SupabaseDataClient | None = Depends(get_execution_db)) -> ExecutionResponse:
        principal.require_scope("executions:read")
        filters = {"id": f"eq.{execution_id}"}
        if principal.api_key:
            filters["project_id"] = f"eq.{principal.api_key.project_id}"
        try:
            if principal.api_key:
                rows = await SupabaseServiceClient().select("executions", select=_execution_select(), filters=filters, limit=1)
            else:
                assert db is not None
                rows = await db.select("executions", select=_execution_select(), filters=filters, limit=1)
            if not rows:
                raise HTTPException(status_code=404, detail="Execution not found")
            return ExecutionResponse.model_validate(ExecutionRecord.from_row(rows[0]).to_response())
        except SupabaseDataError as exc:
            raise _data_error(exc) from exc

    return app


app = create_app()
