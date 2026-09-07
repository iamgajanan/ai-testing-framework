from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from .auth import AuthenticatedUser
from .db import SupabaseDataClient, SupabaseDataError, SupabaseServiceClient, get_data_client


API_KEY_PREFIX = "atk_live_"
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass(frozen=True)
class APIKeyPrincipal:
    key_id: str
    organization_id: str
    project_id: str
    created_by: str
    scopes: tuple[str, ...]
    api_key: str

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes


def generate_api_key() -> tuple[str, str, str]:
    secret = secrets.token_urlsafe(32)
    raw = f"{API_KEY_PREFIX}{secret}"
    prefix = raw[: len(API_KEY_PREFIX) + 8]
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, prefix, digest


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def authenticate_api_key(raw_key: str) -> APIKeyPrincipal | None:
    digest = hash_api_key(raw_key)
    rows = await SupabaseServiceClient().select(
        "project_api_keys",
        select="id,organization_id,project_id,created_by,scopes",
        filters={"key_hash": f"eq.{digest}", "revoked_at": "is.null"},
        limit=1,
    )
    if not rows:
        return None
    row = rows[0]
    scopes = tuple(str(value) for value in (row.get("scopes") or []))
    principal = APIKeyPrincipal(
        key_id=str(row["id"]),
        organization_id=str(row["organization_id"]),
        project_id=str(row["project_id"]),
        created_by=str(row["created_by"]),
        scopes=scopes,
        api_key=raw_key,
    )
    await SupabaseServiceClient().update(
        "project_api_keys",
        {"id": f"eq.{principal.key_id}"},
        {"last_used_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()},
    )
    return principal


async def get_api_key_principal(key: str | None = Depends(api_key_scheme)) -> APIKeyPrincipal:
    if not key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required")
    try:
        principal = await authenticate_api_key(key)
    except SupabaseDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if principal is None:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")
    return principal


def require_scope(principal: APIKeyPrincipal, scope: str) -> None:
    if not principal.has_scope(scope):
        raise HTTPException(status_code=403, detail=f"API key lacks required scope: {scope}")


async def create_project_api_key(
    project_id: UUID,
    name: str,
    user: AuthenticatedUser,
    db: SupabaseDataClient,
) -> dict[str, Any]:
    projects = await db.select(
        "projects",
        select="id,organization_id",
        filters={"id": f"eq.{project_id}"},
        limit=1,
    )
    if not projects:
        raise HTTPException(status_code=404, detail="Project not found")
    raw, prefix, digest = generate_api_key()
    rows = await db.insert(
        "project_api_keys",
        {
            "organization_id": projects[0]["organization_id"],
            "project_id": str(project_id),
            "name": name.strip(),
            "key_prefix": prefix,
            "key_hash": digest,
            "created_by": user.id,
        },
    )
    if not rows:
        raise HTTPException(status_code=502, detail="API key creation failed")
    return {**rows[0], "key": raw}
