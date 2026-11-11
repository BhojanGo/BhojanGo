import uuid
from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from shared import authz
from shared.auth import BearerAuth, InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.service.redis_keys import blacklist_key
from shared.redis import get_redis
from core_api.modules.identity.service.security import decode_token
from shared.db import get_db
from core_api.modules.identity.models.user import User
from core_api.modules.identity.repository.user import UserRepository

logger = structlog.get_logger(__name__)

security = BearerAuth()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(credentials.credentials)
        user_id: str = payload.get("sub", "")
        token_type: str = payload.get("type", "")
        jti: str = payload.get("jti", "")

        if not user_id or token_type != "access":
            raise credentials_exception

        # Check blacklist
        redis = await get_redis()
        if await redis.exists(blacklist_key(jti)):
            raise credentials_exception

    except InvalidTokenError:
        raise credentials_exception

    repo = UserRepository(db)
    user = await repo.get_by_id(uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive account")
    return current_user


class AdminContext:
    """The signed-in admin and their role assignments (read from the database,
    so a revoked role stops working at once, not when the token expires)."""

    def __init__(self, user: User, assignments: list[authz.Assignment]) -> None:
        self.user = user
        self.assignments = assignments

    def can(self, permission: str, scope: str) -> bool:
        return authz.can(self.assignments, permission, scope)

    def require(self, permission: str, scope: str, *, within: bool = False) -> None:
        ok = (authz.can_within if within else authz.can)(self.assignments, permission, scope)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN_SCOPE", "message": f"You need {permission} for {scope}"},
            )


async def get_admin(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminContext:
    from core_api.modules.identity.repository.admin_role import AdminRoleRepository

    rows = await AdminRoleRepository(db).for_user(current_user.id)
    if not rows:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return AdminContext(current_user, [authz.Assignment(r.role, r.scope) for r in rows])


def require_permission(permission: str):  # type: ignore[no-untyped-def]
    """Dependency: an admin who holds ``permission`` somewhere. Check the exact
    scope in the handler with ``admin.require(permission, scope)``."""

    async def dep(admin: Annotated[AdminContext, Depends(get_admin)]) -> AdminContext:
        if not authz.scopes_with(admin.assignments, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": f"You need {permission}"},
            )
        return admin

    return dep


async def require_admin(admin: Annotated[AdminContext, Depends(get_admin)]) -> User:
    """Any admin role (kept for older routes; prefer require_permission)."""
    return admin.user


async def require_restaurant_owner(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    if current_user.role not in ("restaurant_owner", "admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Restaurant owner access required"
        )
    return current_user
