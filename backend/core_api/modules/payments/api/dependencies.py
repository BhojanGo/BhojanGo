"""JWT auth for payment routes. Verification is shared (shared.auth); the 401
body ("Invalid token", no WWW-Authenticate header) is the one payment-svc
returned, unchanged."""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from shared.auth import CurrentUser, InvalidTokenError, decode_access_token

security = HTTPBearer()

__all__ = ["CurrentUser", "get_current_user"]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> CurrentUser:
    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return CurrentUser.from_claims(payload)
