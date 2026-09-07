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

    async def upload_file(self, local_path: str, storage_path: str) -> StoredArtifact:
        path = Path(local_path)
        if not path.is_file():
            raise FileNotFoundError(local_path)
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = path.read_bytes()
        headers = {
            **self._headers,
            "Content-Type": content_type,
            "x-upsert": "true",
            "Cache-Control": "3600",
        }
        url = f"{self._url}/object/{BUCKET}/{quote(storage_path, safe='/')}"
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, headers=headers, content=data)
        if not response.is_success:
            raise SupabaseDataError(f"Storage upload failed: {response.text}", response.status_code)
        return StoredArtifact(path.name, storage_path, content_type, len(data))

    async def create_signed_url(self, storage_path: str, expires_in: int = 3600) -> str:
        url = f"{self._url}/object/sign/{BUCKET}/{quote(storage_path, safe='/')}"
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, headers=self._headers, json={"expiresIn": expires_in})
        if not response.is_success:
            raise SupabaseDataError(f"Storage signing failed: {response.text}", response.status_code)
        payload: dict[str, Any] = response.json()
        signed = payload.get("signedURL") or payload.get("signedUrl")
        if not signed:
            raise SupabaseDataError("Storage did not return a signed URL")
        return signed if signed.startswith("http") else f"{os.environ['SUPABASE_URL'].rstrip('/')}/storage/v1{signed}"
