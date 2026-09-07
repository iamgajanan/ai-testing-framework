from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from .auth import AuthenticatedUser, get_current_user
from .db import SupabaseDataClient, SupabaseDataError, get_data_client
from .storage import SupabaseStorageClient

BUCKET = "test-suites"
MAX_SUITE_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".json", ".yaml", ".yml"}

router = APIRouter(prefix="/v1/projects/{project_id}/test-suites", tags=["test-suites"])


class TestSuiteResponse(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    name: str
    slug: str
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    latest_version: int | None = None


class TestSuiteVersionResponse(BaseModel):
    id: UUID
    test_suite_id: UUID
    version: int
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    created_by: UUID
    created_at: datetime
    signed_url: str | None = None
    expires_in: int | None = None


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value[:80] or "suite"


def _error(exc: SupabaseDataError) -> HTTPException:
    if exc.status_code in {400, 401, 403, 404, 409, 422, 413, 415}:
        return HTTPException(status_code=exc.status_code, detail=str(exc))
    return HTTPException(status_code=502, detail=str(exc))


@router.post("", response_model=TestSuiteVersionResponse, status_code=status.HTTP_201_CREATED)
async def upload_test_suite(
    project_id: UUID,
    file: UploadFile = File(...),
    name: str | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
    db: SupabaseDataClient = Depends(get_data_client),
) -> TestSuiteVersionResponse:
    filename = PurePosixPath(file.filename or "suite.json").name
    extension = PurePosixPath(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Test suite must be .json, .yaml, or .yml")
    data = await file.read(MAX_SUITE_BYTES + 1)
    if len(data) > MAX_SUITE_BYTES:
        raise HTTPException(status_code=413, detail="Test suite exceeds the 10 MB limit")
    if not data:
        raise HTTPException(status_code=400, detail="Test suite is empty")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Test suite must be UTF-8 text") from exc

    suite_name = (name or PurePosixPath(filename).stem).strip()
    if not suite_name or len(suite_name) > 120:
        raise HTTPException(status_code=422, detail="Suite name must be between 1 and 120 characters")
    suite_slug = _slug(suite_name)
    try:
        projects = await db.select(
            "projects",
            select="id,organization_id",
            filters={"id": f"eq.{project_id}"},
            limit=1,
        )
        if not projects:
            raise HTTPException(status_code=404, detail="Project not found")
        project = projects[0]
        suites = await db.select(
            "test_suites",
            select="id,organization_id,project_id,name,slug,created_by,created_at,updated_at",
            filters={"project_id": f"eq.{project_id}", "slug": f"eq.{suite_slug}"},
            limit=1,
        )
        if suites:
            suite = suites[0]
        else:
            suite = (await db.insert("test_suites", {
                "organization_id": project["organization_id"],
                "project_id": str(project_id),
                "name": suite_name,
                "slug": suite_slug,
                "created_by": user.id,
            }))[0]
        versions = await db.select(
            "test_suite_versions",
            select="version",
            filters={"test_suite_id": f"eq.{suite['id']}"},
            order="version.desc",
            limit=1,
        )
        version = int(versions[0]["version"]) + 1 if versions else 1
        digest = hashlib.sha256(data).hexdigest()
        storage_path = f"{project['organization_id']}/{project_id}/{suite['id']}/v{version}/{filename}"
        stored = await SupabaseStorageClient(access_token=user.access_token).upload_bytes(
            data, filename, storage_path, file.content_type, bucket=BUCKET
        )
        rows = await db.insert("test_suite_versions", {
            "test_suite_id": suite["id"],
            "organization_id": project["organization_id"],
            "project_id": str(project_id),
            "version": version,
            "storage_path": stored.storage_path,
            "filename": filename,
            "content_type": stored.content_type,
            "size_bytes": stored.size_bytes,
            "sha256": digest,
            "created_by": user.id,
        })
        return TestSuiteVersionResponse.model_validate(rows[0])
    except SupabaseDataError as exc:
        raise _error(exc) from exc


@router.get("", response_model=list[TestSuiteResponse])
async def list_test_suites(
    project_id: UUID,
    db: SupabaseDataClient = Depends(get_data_client),
) -> list[TestSuiteResponse]:
    try:
        suites = await db.select(
            "test_suites",
            select="id,organization_id,project_id,name,slug,created_by,created_at,updated_at",
            filters={"project_id": f"eq.{project_id}"},
            order="created_at.asc",
        )
        result: list[TestSuiteResponse] = []
        for suite in suites:
            versions = await db.select("test_suite_versions", select="version", filters={"test_suite_id": f"eq.{suite['id']}"}, order="version.desc", limit=1)
            result.append(TestSuiteResponse.model_validate({**suite, "latest_version": int(versions[0]["version"]) if versions else None}))
        return result
    except SupabaseDataError as exc:
        raise _error(exc) from exc


@router.get("/{suite_id}/versions", response_model=list[TestSuiteVersionResponse])
async def list_test_suite_versions(
    project_id: UUID,
    suite_id: UUID,
    db: SupabaseDataClient = Depends(get_data_client),
) -> list[TestSuiteVersionResponse]:
    try:
        rows = await db.select(
            "test_suite_versions",
            select="id,test_suite_id,version,filename,content_type,size_bytes,sha256,created_by,created_at",
            filters={"test_suite_id": f"eq.{suite_id}", "project_id": f"eq.{project_id}"},
            order="version.desc",
        )
        return [TestSuiteVersionResponse.model_validate(row) for row in rows]
    except SupabaseDataError as exc:
        raise _error(exc) from exc


@router.get("/{suite_id}/versions/{version}", response_model=TestSuiteVersionResponse)
async def get_test_suite_version(
    project_id: UUID,
    suite_id: UUID,
    version: int,
    expires_in: int = 3600,
    db: SupabaseDataClient = Depends(get_data_client),
    user: AuthenticatedUser = Depends(get_current_user),
) -> TestSuiteVersionResponse:
    if not 60 <= expires_in <= 86400:
        raise HTTPException(status_code=422, detail="expires_in must be between 60 and 86400 seconds")
    try:
        rows = await db.select(
            "test_suite_versions",
            select="id,test_suite_id,version,filename,storage_path,content_type,size_bytes,sha256,created_by,created_at",
            filters={"test_suite_id": f"eq.{suite_id}", "project_id": f"eq.{project_id}", "version": f"eq.{version}"},
            limit=1,
        )
        if not rows:
            raise HTTPException(status_code=404, detail="Test suite version not found")
        row = rows[0]
        signed_url = await SupabaseStorageClient(access_token=user.access_token).create_signed_url(
            row["storage_path"], expires_in, bucket=BUCKET
        )
        return TestSuiteVersionResponse.model_validate({**row, "signed_url": signed_url, "expires_in": expires_in})
    except SupabaseDataError as exc:
        raise _error(exc) from exc
