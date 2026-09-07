from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from .api_keys import APIKeyPrincipal, authenticate_api_key
from .auth import AuthenticatedUser, get_current_user

bearer_scheme = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass(frozen=True)
class ExecutionPrincipal:
    user: AuthenticatedUser | None = None
    api_key: APIKeyPrincipal | None = None

    @property
    def organization_id(self) -> str | None:
        return self.user.id if self.api_key is None and self.user else self.api_key.organization_id if self.api_key else None

    @property
    def project_id(self) -> str | None:
        return self.api_key.project_id if self.api_key else None

    @property
    def requested_by(self) -> str:
        if self.user:
            return self.user.id
        assert self.api_key is not None
        return self.api_key.created_by

    def require_scope(self, scope: str) -> None:
        if self.api_key and not self.api_key.has_scope(scope):
            raise HTTPException(status_code=403, detail=f"API key lacks required scope: {scope}")


async def get_execution_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    api_key: str | None = Depends(api_key_scheme),
) -> ExecutionPrincipal:
    if credentials is not None:
        return ExecutionPrincipal(user=get_current_user(credentials))
    if api_key:
        principal = await authenticate_api_key(api_key)
        if principal is None:
            raise HTTPException(status_code=401, detail="Invalid or revoked API key")
        return ExecutionPrincipal(api_key=principal)
    raise HTTPException(status_code=401, detail="Authentication required")
