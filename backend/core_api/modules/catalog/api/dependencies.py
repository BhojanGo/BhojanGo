"""JWT auth for catalog routes — catalog does not issue tokens, only validates them.

Verification is shared (shared.auth); the 401 body below is the one
restaurant-svc returned, unchanged.
"""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from shared.auth import BearerAuth, CurrentUser, InvalidTokenError, decode_access_token

security = BearerAuth()

# Who may change a restaurant is decided per restaurant and city in
# catalog/service/access.py, never by role alone.
__all__ = ["CurrentUser", "get_current_user"]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> CurrentUser:
    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return CurrentUser.from_claims(payload)
