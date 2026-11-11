"""JWT auth for worker's notification API. Verification is shared
(shared.auth); the 401 body ("Invalid token") is the one notification-svc
returned, unchanged."""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from shared.auth import BearerAuth, CurrentUser, InvalidTokenError, decode_access_token

security = BearerAuth()

__all__ = ["CurrentUser", "get_current_user"]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> CurrentUser:
    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return CurrentUser.from_claims(payload)
