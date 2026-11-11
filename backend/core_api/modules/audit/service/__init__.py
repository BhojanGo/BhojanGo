"""Write and read the audit log. Every admin change goes through ``record``."""
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.audit.models import AuditLog


async def record(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: str | uuid.UUID,
    scope: str = "*",
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> AuditLog:
    row = AuditLog(
        actor_id=actor_id, action=action, entity_type=entity_type, entity_id=str(entity_id),
        scope=scope, before=before, after=after,
    )
    db.add(row)
    await db.flush()
    return row


async def history(db: AsyncSession, entity_type: str, entity_ids: list[str]) -> list[AuditLog]:
    q = (
        select(AuditLog)
        .where(AuditLog.entity_type == entity_type, AuditLog.entity_id.in_(entity_ids))
        .order_by(AuditLog.at, AuditLog.id)
    )
    return list((await db.execute(q)).scalars())


async def search(db: AsyncSession, *, entity_type: str | None = None, action: str | None = None,
                 limit: int = 100) -> list[AuditLog]:
    q = select(AuditLog).order_by(AuditLog.at.desc()).limit(limit)
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)
    if action:
        q = q.where(AuditLog.action == action)
    return list((await db.execute(q)).scalars())
