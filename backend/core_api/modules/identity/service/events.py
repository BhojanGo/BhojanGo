"""Security events in the audit log (audit module): who signed in, how, and what
changed about their sign-in. entity_type "user", entity_id the account; actor =
the account itself. No passwords, codes, tokens or IP addresses are stored.

Actions (String(40)):
  auth.sign_in            {"method": password | email_code | phone | google | apple | totp | recovery_code}
  auth.sign_in_failed     {"method": ...}   (only for accounts that exist)
  auth.locked             {"minutes": 15}
  auth.signed_up          {"method": "email"}
  auth.email_verified
  auth.password_set / auth.password_changed / auth.password_reset
  auth.email_linked / auth.phone_linked
  auth.mfa_enabled / auth.mfa_used / auth.mfa_recovery_used / auth.mfa_codes_renewed
"""
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.service import background

ENTITY = "user"


async def record(db: AsyncSession, user_id: uuid.UUID, action: str, **details: Any) -> None:
    """In the request's transaction (committed with the change it describes)."""
    from core_api.modules.audit import service as audit

    await audit.record(db, actor_id=user_id, action=action, entity_type=ENTITY, entity_id=user_id,
                       after=details or None)


async def _record_own_session(user_id: uuid.UUID, action: str, details: dict[str, Any]) -> None:
    from core_api.modules.audit import service as audit
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await audit.record(db, actor_id=user_id, action=action, entity_type=ENTITY, entity_id=user_id,
                           after=details or None)
        await db.commit()


def record_later(user_id: uuid.UUID, action: str, **details: Any) -> None:
    """In its own transaction, after the answer: for failures (the request's own
    transaction is rolled back) and where timing must not depend on the account."""
    background.spawn(_record_own_session(user_id, action, details), name=f"audit:{action}")
