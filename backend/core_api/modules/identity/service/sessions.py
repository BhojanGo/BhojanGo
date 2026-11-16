"""Sessions: issuing tokens, signing out everywhere, and who needs the second step.

Tokens (P5): RS256 access tokens for 15 minutes and rotating refresh tokens.
Every sign-in starts a refresh-token *family*; each refresh returns a new
token in that family and retires the old one. Presenting a retired token
means it leaked, so the whole family is revoked.

Two-step sign-in (Round 8, D5): an account with admin roles only gets tokens
after its second step (service/mfa.py). Such tokens carry ``mfa: true`` and the
``adm`` role list; get_admin refuses an admin token without ``mfa``, and a
refresh token without it can't be refreshed by an admin.

Redis keys (service/redis_keys.py):
  refresh_family:{user}:{family} -> current jti   (TTL = refresh lifetime)
  refresh_families:{user}        -> set of family ids (for sign-out everywhere)
"""
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.models.user import User
from core_api.modules.identity.repository.admin_role import AdminRoleRepository
from core_api.modules.identity.schemas.user import AuthTokensResponse, UserResponse
from core_api.modules.identity.service.redis_keys import blacklist_key, refresh_families_key, refresh_family_key
from core_api.modules.identity.service.security import create_access_token, create_refresh_token, decode_token
from shared.auth import InvalidTokenError
from shared.redis import get_redis

ADMIN_PERSONAS = ("admin", "super_admin")


async def admin_roles(db: AsyncSession, user: User) -> list[str]:
    return [f"{a.role}@{a.scope}" for a in await AdminRoleRepository(db).for_user(user.id)]


async def requires_mfa(db: AsyncSession, user: User) -> bool:
    """Admins (any admin role, or the admin persona) sign in with a second step."""
    return user.role in ADMIN_PERSONAS or bool(await admin_roles(db, user))


async def issue_tokens(db: AsyncSession, user: User, *, family: str | None = None, is_new_user: bool = False,
                       mfa: bool = False) -> AuthTokensResponse:
    """Access + refresh token pair; starts a new refresh family unless one is given.
    Refuses an admin account unless its second step was passed (``mfa``)."""
    admin = await admin_roles(db, user)
    if (admin or user.role in ADMIN_PERSONAS) and not mfa:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail={"code": "MFA_REQUIRED", "message": "Sign in again with your authenticator code"})
    access_token, expires_in = create_access_token(str(user.id), user.email, user.role, user.country, admin, mfa=mfa)
    refresh_token, jti, family, ttl = create_refresh_token(str(user.id), family, mfa=mfa)
    redis = await get_redis()
    uid = str(user.id)
    pipe = redis.pipeline()
    pipe.setex(refresh_family_key(uid, family), ttl, jti)
    pipe.sadd(refresh_families_key(uid), family)
    pipe.expire(refresh_families_key(uid), ttl)
    await pipe.execute()
    return AuthTokensResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
        is_new_user=is_new_user,
        admin_roles=admin,
    )


async def revoke_all_sessions(user_id: str) -> None:
    """Sign out everywhere: drop every refresh family of the user."""
    redis = await get_redis()
    families = await redis.smembers(refresh_families_key(user_id))
    keys = [refresh_family_key(user_id, f) for f in families] + [refresh_families_key(user_id)]
    await redis.delete(*keys)


async def blacklist_access_token(access_token: str) -> None:
    try:
        payload = decode_token(access_token)
    except InvalidTokenError:
        return
    ttl = max(0, int(payload.get("exp", 0) - datetime.now(UTC).timestamp()))
    if ttl > 0:
        redis = await get_redis()
        await redis.setex(blacklist_key(payload.get("jti", "")), ttl, "1")


def token_has_mfa(access_token: str) -> bool:
    try:
        return decode_token(access_token).get("mfa") is True
    except InvalidTokenError:
        return False
