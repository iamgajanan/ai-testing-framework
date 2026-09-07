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
        self._rpc_url = f"{url}/rest/v1/rpc"
        self._headers = {
            "apikey": key,
            "Authorization": f"Bearer {user.access_token}",
            "Content-Type": "application/json",
        }

    async def select(self, table: str, *, select: str = "*", filters: dict[str, str] | None = None, order: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        params: dict[str, str] = {"select": select}
        if filters:
            params.update(filters)
        if order:
            params["order"] = order
        if limit is not None:
            params["limit"] = str(limit)
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{self._url}/{table}", headers=self._headers, params=params)
        return self._parse(response)

    async def insert(self, table: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        headers = {**self._headers, "Prefer": "return=representation"}
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(f"{self._url}/{table}", headers=headers, json=payload)
        return self._parse(response)

    async def update(self, table: str, filters: dict[str, str], payload: dict[str, Any]) -> list[dict[str, Any]]:
        headers = {**self._headers, "Prefer": "return=representation"}
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.patch(f"{self._url}/{table}", headers=headers, params=filters, json=payload)
        return self._parse(response)

    async def rpc(self, function: str, payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(f"{self._rpc_url}/{function}", headers=self._headers, json=payload or {})
        return self._parse(response)

    @staticmethod
    def _parse(response: httpx.Response) -> list[dict[str, Any]]:
        if response.is_success:
            if not response.content:
                return []
            data = response.json()
            if data is None:
                return []
            return data if isinstance(data, list) else [data]
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        raise SupabaseDataError(str(detail), response.status_code)


def get_data_client(user: AuthenticatedUser = Depends(get_current_user)) -> SupabaseDataClient:
    return SupabaseDataClient(user)


class SupabaseServiceClient:
    """Server-only service client. Never expose the service-role key to clients."""

    def __init__(self) -> None:
        url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not url or not key:
            raise SupabaseDataError("Server database integration is not configured", 503)
        self._url = f"{url}/rest/v1"
        self._rpc_url = f"{url}/rest/v1/rpc"
        self._headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    async def select(self, table: str, *, select: str = "*", filters: dict[str, str] | None = None, order: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        params: dict[str, str] = {"select": select}
        if filters:
            params.update(filters)
        if order:
            params["order"] = order
        if limit is not None:
            params["limit"] = str(limit)
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{self._url}/{table}", headers=self._headers, params=params)
        return SupabaseDataClient._parse(response)

    async def insert(self, table: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        headers = {**self._headers, "Prefer": "return=representation"}
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(f"{self._url}/{table}", headers=headers, json=payload)
        return SupabaseDataClient._parse(response)

    async def update(self, table: str, filters: dict[str, str], payload: dict[str, Any]) -> list[dict[str, Any]]:
        headers = {**self._headers, "Prefer": "return=representation"}
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.patch(f"{self._url}/{table}", headers=headers, params=filters, json=payload)
        return SupabaseDataClient._parse(response)


class SupabaseWorkerClient:
    """Server-only queue client. Never expose the service-role key to clients."""

    def __init__(self) -> None:
        url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not url or not key:
            raise SupabaseDataError("Worker database integration is not configured", 503)
        self._rpc_url = f"{url}/rest/v1/rpc"
        self._headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    async def claim_next_execution(self) -> list[dict[str, Any]]:
        return await self._rpc("claim_next_execution", {})

    async def complete_execution(self, execution_id: str, status: str, result: dict[str, Any] | None = None, error: str | None = None) -> list[dict[str, Any]]:
        return await self._rpc("complete_execution", {"target_execution_id": execution_id, "target_status": status, "target_result": result, "target_error": error})

    async def _rpc(self, function: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(f"{self._rpc_url}/{function}", headers=self._headers, json=payload)
        return SupabaseDataClient._parse(response)
