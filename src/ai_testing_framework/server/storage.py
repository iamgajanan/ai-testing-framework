from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from .db import SupabaseDataError


BUCKET = "execution-artifacts"


def _publishable_key() -> str:
    """Return the configured browser-safe Supabase key.

    Supabase projects may expose either the newer publishable key name or the
    legacy anon key name. Supporting both keeps existing local deployments
    working without weakening the server-side authorization checks.
    """
    return os.environ.get("SUPABASE_PUBLISHABLE_KEY", "") or os.environ.get("SUPABASE_ANON_KEY", "")


def _service_role_key() -> str:
    """Return the configured server-only Supabase privileged key."""
    return os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "") or os.environ.get("SUPABASE_SECRET_KEY", "")


@dataclass(frozen=True)
class StoredArtifact:
    name: str
    storage_path: str
    content_type: str
    size_bytes: int


class SupabaseStorageClient:
    """Supabase Storage client.

    Worker/server operations use the service-role key. Authenticated dashboard
    requests can instead pass the user's JWT, so suite uploads/downloads do not
    require a privileged key in the local dashboard flow.
    """

    def __init__(self, access_token: str | None = None) -> None:
        url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        if not url:
            raise SupabaseDataError("SUPABASE_URL is not configured", 503)

        if access_token:
            key = _publishable_key()
            if not key:
                raise SupabaseDataError(
                    "Supabase client key is not configured. Set SUPABASE_PUBLISHABLE_KEY "
                    "or SUPABASE_ANON_KEY in the FastAPI environment.",
                    503,
                )
            self._headers = {"apikey": key, "Authorization": f"Bearer {access_token}"}
        else:
            key = _service_role_key()
            if not key:
                raise SupabaseDataError(
                    "Supabase server key is not configured. Set SUPABASE_SERVICE_ROLE_KEY "
                    "or SUPABASE_SECRET_KEY in the worker environment.",
                    503,
                )
            self._headers = {"apikey": key, "Authorization": f"Bearer {key}"}
        self._url = f"{url}/storage/v1"

    async def upload_file(self, local_path: str, storage_path: str, bucket: str = BUCKET) -> StoredArtifact:
        path = Path(local_path)
        if not path.is_file():
            raise FileNotFoundError(local_path)
        data = path.read_bytes()
        return await self.upload_bytes(data, path.name, storage_path, None, bucket=bucket)

    async def upload_bytes(
        self,
        data: bytes,
        filename: str,
        storage_path: str,
        content_type: str | None = None,
        *,
        bucket: str = "test-suites",
    ) -> StoredArtifact:
        guessed = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        resolved_content_type = content_type or guessed
        headers = {
            **self._headers,
            "Content-Type": resolved_content_type,
            "x-upsert": "false",
            "Cache-Control": "3600",
        }
        url = f"{self._url}/object/{quote(bucket, safe='')}/{quote(storage_path, safe='/')}"
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, headers=headers, content=data)
        if not response.is_success:
            raise SupabaseDataError(f"Storage upload failed: {response.text}", response.status_code)
        return StoredArtifact(filename, storage_path, resolved_content_type, len(data))

    async def download_bytes(self, storage_path: str, *, bucket: str = "test-suites") -> bytes:
        url = f"{self._url}/object/{quote(bucket, safe='')}/{quote(storage_path, safe='/')}"
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.get(url, headers=self._headers)
        if not response.is_success:
            raise SupabaseDataError(f"Storage download failed: {response.text}", response.status_code)
        return response.content

    async def create_signed_url(self, storage_path: str, expires_in: int = 3600, bucket: str = BUCKET) -> str:
        url = f"{self._url}/object/sign/{quote(bucket, safe='')}/{quote(storage_path, safe='/')}"
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, headers=self._headers, json={"expiresIn": expires_in})
        if not response.is_success:
            raise SupabaseDataError(f"Storage signing failed: {response.text}", response.status_code)
        payload: dict[str, Any] = response.json()
        signed = payload.get("signedURL") or payload.get("signedUrl")
        if not signed:
            raise SupabaseDataError("Storage did not return a signed URL")
        return signed if signed.startswith("http") else f"{os.environ['SUPABASE_URL'].rstrip('/')}/storage/v1{signed}"
