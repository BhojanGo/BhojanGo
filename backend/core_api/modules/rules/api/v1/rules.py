"""Rules API (P7). Permissions, always at the rule's market (its city for
zone and restaurant rules):

  read                          rules.view
  create / edit / submit        rules.edit
  approve / reject / end        rules.approve, and not the admin who made it
  platform-wide rules           the permission at "*" (super admin)
"""
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.audit import service as audit
from core_api.modules.identity.api.dependencies import AdminContext, require_permission
from core_api.modules.rules.models import Rule
from core_api.modules.rules.schemas import (
    ApprovalOut,
    AuditOut,
    Decision,
    EndRule,
    NewVersion,
    Rejection,
    ResolvedRule,
    RuleCreate,
    RuleHistory,
    RuleOut,
    RuleUpdate,
)
from core_api.modules.rules.service import templates
from core_api.modules.rules.service.resolver import Context
from core_api.modules.rules.service.rules import RuleError, RuleNotFound, RuleService
from shared import authz
from shared.db import get_db

router = APIRouter(prefix="/rules", tags=["Rules"])

DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
Viewer = Annotated[AdminContext, Depends(require_permission("rules.view"))]
Editor = Annotated[AdminContext, Depends(require_permission("rules.edit"))]
Approver = Annotated[AdminContext, Depends(require_permission("rules.approve"))]


def out(r: Rule) -> RuleOut:
    return RuleOut.model_validate(r).model_copy(update={"money": r.family in templates.MONEY_FAMILIES})


async def _run(coro):  # type: ignore[no-untyped-def]
    try:
        return await coro
    except RuleNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND", "message": str(e)})
    except templates.TemplateError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": "INVALID_RULE", "message": str(e)})
    except RuleError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "RULE_WORKFLOW", "message": str(e)})
    except ValueError as e:  # pydantic validation of template params
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": "INVALID_PARAMS", "message": str(e)})


async def _rule_for(admin: AdminContext, db: AsyncSession, rule_id: uuid.UUID, permission: str) -> Rule:
    r = await _run(RuleService(db).get(rule_id))
    admin.require(permission, r.market_scope)
    return r


@router.get("/templates")
async def list_templates(admin: Viewer) -> list[dict]:
    """Every template with its parameter schema, allowed levels and whether it moves money."""
    return templates.catalogue()


@router.get("", response_model=list[RuleOut])
async def list_rules(
    admin: Viewer, db: DB,
    family: str | None = None,
    rule_status: str | None = Query(default=None, alias="status"),
    scope: str | None = Query(default=None, description="Only rules at or inside this market code"),
    all_versions: bool = False,
) -> list[RuleOut]:
    """Rules you can see (latest version of each, unless all_versions)."""
    rows = await RuleService(db).list_rules(family=family, status=rule_status, market_scope=scope, latest_only=not all_versions)
    visible = authz.scopes_with(admin.assignments, "rules.view")
    return [out(r) for r in rows if any(authz.covers(v, r.market_scope) for v in visible)]


@router.get("/approvals", response_model=list[RuleOut])
async def approval_queue(admin: Approver, db: DB) -> list[RuleOut]:
    """Versions waiting for a second admin, in scopes you can approve, not made by you."""
    rows = await RuleService(db).pending()
    return [out(r) for r in rows if admin.can("rules.approve", r.market_scope) and r.created_by != admin.user.id]


@router.get("/resolve", response_model=list[ResolvedRule])
async def resolve_rules(
    admin: Viewer, db: DB,
    country: str | None = None, region: str | None = None, city: str | None = None,
    zone_id: str | None = None, restaurant_id: str | None = None,
    at: datetime | None = None,
    draft: list[uuid.UUID] = Query(default=[], description="Draft rule ids to try as if live"),
) -> list[ResolvedRule]:
    """The rule that applies in each slot for this place and time."""
    admin.require("rules.view", city or region or country or "*", within=True)
    ctx = Context(country=country, region=region, city=city, zone_id=zone_id, restaurant_id=restaurant_id)
    picked = await RuleService(db).resolve(ctx, at, overlay_ids=draft)
    return [
        ResolvedRule(slot=slot, rule_id=c.id, rule_key=c.rule_key, version=c.version, family=c.family,
                     template=c.template, name=c.name, params=c.params, scope_level=c.scope_level, scope_id=c.scope_id)
        for slot, c in sorted(picked.items())
    ]


@router.post("", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(data: RuleCreate, admin: Editor, db: DB) -> RuleOut:
    svc = RuleService(db)
    market_scope = await _run(svc.market_scope_for(data.scope_level, data.scope_id))
    admin.require("rules.edit", market_scope)
    r = await _run(svc.create(admin.user.id, **data.model_dump()))
    return out(r)


@router.get("/{rule_id}", response_model=RuleOut)
async def get_rule(rule_id: uuid.UUID, admin: Viewer, db: DB) -> RuleOut:
    return out(await _rule_for(admin, db, rule_id, "rules.view"))


@router.get("/{rule_id}/history", response_model=RuleHistory)
async def rule_history(rule_id: uuid.UUID, admin: Viewer, db: DB) -> RuleHistory:
    """Every version, approval and change of this rule."""
    r = await _rule_for(admin, db, rule_id, "rules.view")
    svc = RuleService(db)
    versions = await svc.versions(r.rule_key)
    return RuleHistory(
        versions=[out(v) for v in versions],
        approvals={str(v.id): [ApprovalOut.model_validate(a) for a in await svc.approvals(v.id)] for v in versions},
        audit=[AuditOut.model_validate(a) for a in await audit.history(db, "rule", [str(r.rule_key)])],
    )


@router.patch("/{rule_id}", response_model=RuleOut)
async def edit_draft(rule_id: uuid.UUID, data: RuleUpdate, admin: Editor, db: DB) -> RuleOut:
    await _rule_for(admin, db, rule_id, "rules.edit")
    return out(await _run(RuleService(db).update_draft(admin.user.id, rule_id, data.model_dump(exclude_unset=True))))


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def discard_draft(rule_id: uuid.UUID, admin: Editor, db: DB) -> None:
    await _rule_for(admin, db, rule_id, "rules.edit")
    await _run(RuleService(db).discard(admin.user.id, rule_id))


@router.post("/{rule_id}/versions", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
async def new_version(rule_id: uuid.UUID, data: NewVersion, admin: Editor, db: DB) -> RuleOut:
    """Change a published rule: a new draft version, published on review."""
    await _rule_for(admin, db, rule_id, "rules.edit")
    return out(await _run(RuleService(db).new_version(admin.user.id, rule_id, **data.model_dump())))


@router.post("/{rule_id}/submit", response_model=RuleOut)
async def submit(rule_id: uuid.UUID, admin: Editor, db: DB) -> RuleOut:
    """Money rules go to a second admin; business rules are published at once."""
    await _rule_for(admin, db, rule_id, "rules.edit")
    return out(await _run(RuleService(db).submit(admin.user.id, rule_id)))


@router.post("/{rule_id}/approve", response_model=RuleOut)
async def approve(rule_id: uuid.UUID, data: Decision, admin: Approver, db: DB) -> RuleOut:
    await _rule_for(admin, db, rule_id, "rules.approve")
    return out(await _run(RuleService(db).approve(admin.user.id, rule_id, data.note)))


@router.post("/{rule_id}/reject", response_model=RuleOut)
async def reject(rule_id: uuid.UUID, data: Rejection, admin: Approver, db: DB) -> RuleOut:
    await _rule_for(admin, db, rule_id, "rules.approve")
    return out(await _run(RuleService(db).reject(admin.user.id, rule_id, data.note)))


@router.post("/{rule_id}/rollback", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
async def rollback(rule_id: uuid.UUID, admin: Editor, db: DB) -> RuleOut:
    """Bring back this (earlier) version, starting now. Money rules go for approval."""
    await _rule_for(admin, db, rule_id, "rules.edit")
    return out(await _run(RuleService(db).rollback(admin.user.id, rule_id)))


@router.post("/{rule_id}/end", response_model=RuleOut)
async def end_rule(rule_id: uuid.UUID, data: EndRule, admin: Approver, db: DB) -> RuleOut:
    """Stop a published rule now or at a set time (e.g. end a promotion)."""
    await _rule_for(admin, db, rule_id, "rules.approve")
    return out(await _run(RuleService(db).end(admin.user.id, rule_id, data.at)))


# ── Audit log ─────────────────────────────────────────────────────────────────

audit_router = APIRouter(prefix="/audit", tags=["Audit log"])


@audit_router.get("", response_model=list[AuditOut])
async def audit_log(
    admin: Annotated[AdminContext, Depends(require_permission("audit.view"))], db: DB,
    entity_type: str | None = None, action: str | None = None, limit: int = Query(default=100, le=500),
) -> list[AuditOut]:
    """Every admin change, newest first (Settings ▸ Audit log; super admins)."""
    rows = await audit.search(db, entity_type=entity_type, action=action, limit=limit)
    visible = authz.scopes_with(admin.assignments, "audit.view")
    return [AuditOut.model_validate(a) for a in rows if any(authz.covers(v, a.scope) for v in visible)]
