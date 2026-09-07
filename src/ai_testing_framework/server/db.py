from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import Depends

from .auth import AuthenticatedUser, get_current_user


class SupabaseDataError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class SupabaseDataClient:
    def __init__(self, user: AuthenticatedUser) -> None:
        url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
        if not url or not key:
            raise SupabaseDataError("Database integration is not configured", 503)
        self._url = f"{url}/rest/v1"
        self._headers = {
            "apikey": key,
            "Authorization": f"Bearer {user.access_token}",
            "Content-Type": "application/json",
        }

    async def select(
        self,
        table: str,
        *,
        select: str = "*",
        filters: dict[str, str] | None = None,
        order: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {"select": select}
        if filters:
            params.update(filters)
        if order:
            params["order"] = order
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{self._url}/{table}", headers=self._headers, params=params)
        return self._parse(response)

    async def insert(self, table: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        headers = {**self._headers, "Prefer": "return=representation"}
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(f"{self._url}/{table}", headers=headers, json=payload)
        return self._parse(response)

    @staticmethod
    def _parse(response: httpx.Response) -> list[dict[str, Any]]:
        if response.is_success:
            data = response.json()
            return data if isinstance(data, list) else [data]
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        raise SupabaseDataError(str(detail), response.status_code)


def get_data_client(user: AuthenticatedUser = Depends(get_current_user)) -> SupabaseDataClient:
    return SupabaseDataClient(user)
