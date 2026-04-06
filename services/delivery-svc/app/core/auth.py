import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import get_settings

settings = get_settings()
security = HTTPBearer()


class CurrentUser:
    def __init__(self, user_id: str, role: str, country: str) -> None:
        self.user_id = user_id
        self.role = role
        self.country = country
        self.id = uuid.UUID(user_id)


def _decode_token(token: str) -> CurrentUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub", "")
        if not user_id or payload.get("type") != "access":
            raise credentials_exception
        return CurrentUser(user_id=user_id, role=payload.get("role", "customer"), country=payload.get("country", "US"))
    except JWTError:
        raise credentials_exception


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> CurrentUser:
    return _decode_token(credentials.credentials)


async def get_ws_user(token: str = Query(...)) -> CurrentUser:
    """For WebSocket auth via ?token=... query param."""
    return _decode_token(token)
