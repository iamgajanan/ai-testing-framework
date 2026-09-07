from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    email: str | None
    claims: dict[str, Any]


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    if not url:
        raise RuntimeError("SUPABASE_URL is required for JWT verification")
    return PyJWKClient(f"{url}/auth/v1/.well-known/jwks.json")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    if not supabase_url:
        raise HTTPException(status_code=503, detail="Authentication is not configured")

    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(credentials.credentials)
        claims = jwt.decode(
            credentials.credentials,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
            issuer=f"{supabase_url}/auth/v1",
            options={"require": ["sub", "exp", "iat"]},
        )
    except (jwt.PyJWTError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return AuthenticatedUser(
        id=str(claims["sub"]),
        email=claims.get("email"),
        claims=claims,
    )
