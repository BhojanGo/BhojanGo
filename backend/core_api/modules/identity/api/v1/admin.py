"""Admin roles: who can do what, where (shared/authz.py has the rules)."""
import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.api.dependencies import AdminContext, get_admin, require_permission
from core_api.modules.identity.repository.admin_role import AdminRoleRepository
from core_api.modules.identity.repository.user import UserRepository
from core_api.modules.identity.schemas.admin import AdminMeResponse, RoleAssignmentCreate, RoleAssignmentResponse
from shared import authz
from shared.db import get_db

router = APIRouter(prefix="/admin", tags=["Admin roles"])
logger = structlog.get_logger(__name__)

ALL_PERMISSIONS = sorted({p for perms in authz.PERMISSIONS.values() for p in perms if p != "*"})


@router.get("/me", response_model=AdminMeResponse)
async def admin_me(
    admin: Annotated[AdminContext, Depends(get_admin)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> AdminMeResponse:
    """My admin roles, and for each permission the widest scopes where I hold it.
    The admin console uses this to build the scope bar and hide what I can't do."""
    rows = await AdminRoleRepository(db).for_user(admin.user.id)
    perms = {p: authz.scopes_with(admin.assignments, p) for p in ALL_PERMISSIONS}
    return AdminMeResponse(
        user_id=admin.user.id,
        email=admin.user.email,
        full_name=admin.user.full_name,
        assignments=[RoleAssignmentResponse.model_validate(r) for r in rows],
        permissions={p: s for p, s in perms.items() if s},
    )


@router.get("/role-assignments", response_model=list[RoleAssignmentResponse])
async def list_assignments(
    admin: Annotated[AdminContext, Depends(require_permission("admins.view"))],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    scope: str | None = Query(default=None, description="Only assignments at or inside this scope"),
) -> list[RoleAssignmentResponse]:
    """Assignments I can see: those inside the scopes where I hold admins.view."""
    visible = authz.scopes_with(admin.assignments, "admins.view")
    rows = await AdminRoleRepository(db).list_all()
    out = [
        r for r in rows
        if any(authz.covers(v, r.scope) for v in visible) and (scope is None or authz.covers(scope, r.scope))
    ]
    return [RoleAssignmentResponse.model_validate(r) for r in out]


@router.post("/role-assignments", response_model=RoleAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def grant_role(
    data: RoleAssignmentCreate,
    admin: Annotated[AdminContext, Depends(get_admin)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> RoleAssignmentResponse:
    """Grant a role at a scope. Super admins grant anything; country managers
    grant city ops, support, finance and viewer inside their country."""
    try:
        authz.validate_assignment(data.role, data.scope)
    except authz.ScopeError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": "INVALID_ROLE", "message": str(e)})
    if not authz.can_grant(admin.assignments, data.role, data.scope):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN_SCOPE", "message": f"You can't grant {data.role} at {data.scope}"},
        )

    users = UserRepository(db)
    if data.user_id:
        target = await users.get_by_id(data.user_id)
    elif data.email:
        target = await users.get_by_email(data.email)
    else:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Give user_id or email")
    if not target or not target.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    repo = AdminRoleRepository(db)
    existing = await repo.find(target.id, data.role, data.scope)
    if existing:
        return RoleAssignmentResponse.model_validate(existing)
    row = await repo.create(user_id=target.id, role=data.role, scope=data.scope, granted_by=admin.user.id)
    if target.role == "customer":
        await users.update(target.id, role="admin")
    logger.info("admin_role_granted", user_id=str(target.id), role=data.role, scope=data.scope, by=str(admin.user.id))
    return RoleAssignmentResponse.model_validate(row)


@router.delete("/role-assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_role(
    assignment_id: uuid.UUID,
    admin: Annotated[AdminContext, Depends(get_admin)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> None:
    """Revoke a role. Same rule as granting it. Takes effect at once for
    core_api (roles are read from the database on each request)."""
    repo = AdminRoleRepository(db)
    row = await repo.get(assignment_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    if not authz.can_grant(admin.assignments, row.role, row.scope):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN_SCOPE", "message": f"You can't revoke {row.role} at {row.scope}"},
        )
    await repo.delete(assignment_id)
    logger.info("admin_role_revoked", user_id=str(row.user_id), role=row.role, scope=row.scope, by=str(admin.user.id))
