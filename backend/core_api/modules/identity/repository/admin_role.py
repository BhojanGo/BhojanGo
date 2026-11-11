import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.models.admin_role import AdminRoleAssignment


class AdminRoleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def for_user(self, user_id: uuid.UUID) -> list[AdminRoleAssignment]:
        result = await self.session.execute(
            select(AdminRoleAssignment).where(AdminRoleAssignment.user_id == user_id).order_by(AdminRoleAssignment.created_at)
        )
        return list(result.scalars().all())

    async def get(self, assignment_id: uuid.UUID) -> AdminRoleAssignment | None:
        return await self.session.get(AdminRoleAssignment, assignment_id)

    async def find(self, user_id: uuid.UUID, role: str, scope: str) -> AdminRoleAssignment | None:
        result = await self.session.execute(
            select(AdminRoleAssignment).where(
                AdminRoleAssignment.user_id == user_id,
                AdminRoleAssignment.role == role,
                AdminRoleAssignment.scope == scope,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, **kwargs) -> AdminRoleAssignment:  # type: ignore[no-untyped-def]
        row = AdminRoleAssignment(**kwargs)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def list_all(self) -> list[AdminRoleAssignment]:
        result = await self.session.execute(select(AdminRoleAssignment).order_by(AdminRoleAssignment.scope))
        return list(result.scalars().all())

    async def delete(self, assignment_id: uuid.UUID) -> None:
        await self.session.execute(delete(AdminRoleAssignment).where(AdminRoleAssignment.id == assignment_id))

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        await self.session.execute(delete(AdminRoleAssignment).where(AdminRoleAssignment.user_id == user_id))
