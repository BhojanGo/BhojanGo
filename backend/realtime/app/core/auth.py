"""JWT auth for realtime HTTP and WebSocket routes.

Verification is shared (shared.auth); the 401 body ("Invalid credentials") is
the one delivery-svc returned, unchanged.
"""
from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from shared.auth import CurrentUser, InvalidTokenError, decode_access_token

security = HTTPBearer()

__all__ = ["CurrentUser", "get_current_user", "get_ws_user"]


def _decode_token(token: str) -> CurrentUser:
    try:
        payload = decode_access_token(token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    return CurrentUser.from_claims(payload)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> CurrentUser:
    return _decode_token(credentials.credentials)


async def get_ws_user(token: str = Query(...)) -> CurrentUser:
    """For WebSocket auth via ?token=... query param."""
    return _decode_token(token)
