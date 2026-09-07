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


@dataclass(frozen=True)
class StoredArtifact:
    name: str
    storage_path: str
    content_type: str
    size_bytes: int


class SupabaseStorageClient:
    """Server-only Supabase Storage client using the service role key."""

    def __init__(self) -> None:
        url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not url or not key:
            raise SupabaseDataError("Artifact storage is not configured", 503)
        self._url = f"{url}/storage/v1"
        self._headers = {"apikey": key, "Authorization": f"Bearer {key}"}

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
            "x-upsert": "true",
            "Cache-Control": "3600",
        }
        url = f"{self._url}/object/{quote(bucket, safe='')}/{quote(storage_path, safe='/')}"
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, headers=headers, content=data)
        if not response.is_success:
            raise SupabaseDataError(f"Storage upload failed: {response.text}", response.status_code)
        return StoredArtifact(filename, storage_path, resolved_content_type, len(data))

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
