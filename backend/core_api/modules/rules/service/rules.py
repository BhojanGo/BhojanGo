"""Rule lifecycle: draft -> (review) -> publish, versions, rollback, resolve.

Other modules (pricing in P8, orders, dispatch) call ``RuleService.resolve``
to get the rules that apply to an order; they never read the tables.
"""
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.audit import service as audit
from core_api.modules.markets.service.markets import MarketService, NotFound
from core_api.modules.rules.models import Rule, RuleApproval
from core_api.modules.rules.service import templates
from core_api.modules.rules.service.resolver import Candidate, Context, resolve

OPEN_STATUSES = ("draft", "pending_approval")


class RuleError(ValueError):
    """A change the rule workflow doesn't allow; shown to admins as is."""


class RuleNotFound(LookupError):
    pass


def now() -> datetime:
    return datetime.now(UTC)


def snapshot(r: Rule) -> dict[str, Any]:
    return {
        "id": str(r.id), "rule_key": str(r.rule_key), "version": r.version, "family": r.family,
        "template": r.template, "key": r.key, "name": r.name, "params": r.params, "scope_level": r.scope_level,
        "scope_id": r.scope_id, "priority": r.priority, "locked": r.locked, "status": r.status,
        "effective_from": r.effective_from.isoformat() if r.effective_from else None,
        "effective_to": r.effective_to.isoformat() if r.effective_to else None,
        "paused": r.paused_at is not None, "paused_reason": r.paused_reason,
    }


def candidate(r: Rule) -> Candidate:
    return Candidate(
        id=r.id, rule_key=r.rule_key, version=r.version, family=r.family, template=r.template, slot=r.slot,
        params=r.params, scope_level=r.scope_level, scope_id=r.scope_id, priority=r.priority, locked=r.locked,
        status=r.status, effective_from=r.effective_from, effective_to=r.effective_to, name=r.name,
    )


class RuleService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── scope ────────────────────────────────────────────────────────────────
    async def market_scope_for(self, level: str, scope_id: str) -> str:
        """Check the scope exists; return the market code that owns it."""
        markets = MarketService(self.db)
        if level == "platform":
            if scope_id != "*":
                raise RuleError('A platform rule has scope_id "*"')
            return "*"
        if level == "country":
            if not await markets.repo.country(scope_id):
                raise RuleError(f"Country {scope_id} not found")
            return scope_id
        if level == "region":
            if not await markets.repo.region(scope_id):
                raise RuleError(f"State {scope_id} not found")
            return scope_id
        if level == "city":
            if not await markets.repo.city(scope_id):
                raise RuleError(f"City {scope_id} not found")
            return scope_id
        if level == "zone":
            try:
                return await markets.zone_city_code(uuid.UUID(scope_id))
            except (NotFound, ValueError):
                raise RuleError("Zone not found")
        if level == "restaurant":
            from core_api.modules.catalog.service.lookup import restaurant_city_code

            code = await restaurant_city_code(self.db, scope_id)
            if not code:
                raise RuleError("Restaurant not found, or it isn't inside any city we serve")
            return code
        raise RuleError(f"Unknown scope level {level!r}")

    # ── reads ────────────────────────────────────────────────────────────────
    async def get(self, rule_id: uuid.UUID) -> Rule:
        r = await self.db.get(Rule, rule_id)
        if not r:
            raise RuleNotFound("Rule not found")
        return r

    async def versions(self, rule_key: uuid.UUID) -> list[Rule]:
        q = select(Rule).where(Rule.rule_key == rule_key).order_by(Rule.version)
        return list((await self.db.execute(q)).scalars())

    async def list_rules(self, *, family: str | None = None, status: str | None = None,
                   market_scope: str | None = None, latest_only: bool = True) -> list[Rule]:
        q = select(Rule)
        if family:
            q = q.where(Rule.family == family)
        if status:
            q = q.where(Rule.status == status)
        if market_scope:
            q = q.where(or_(Rule.market_scope == market_scope, Rule.market_scope.like(market_scope + "-%")))
        rows = list((await self.db.execute(q.order_by(Rule.family, Rule.slot, Rule.version))).scalars())
        if not latest_only:
            return rows
        latest: dict[uuid.UUID, Rule] = {}
        for r in rows:
            latest[r.rule_key] = r
        return list(latest.values())

    async def approvals(self, rule_id: uuid.UUID) -> list[RuleApproval]:
        q = select(RuleApproval).where(RuleApproval.rule_id == rule_id).order_by(RuleApproval.requested_at)
        return list((await self.db.execute(q)).scalars())

    async def pending(self) -> list[Rule]:
        q = select(Rule).where(Rule.status == "pending_approval").order_by(Rule.updated_at)
        return list((await self.db.execute(q)).scalars())

    # ── drafts ───────────────────────────────────────────────────────────────
    async def create(self, actor: uuid.UUID, *, family: str, template: str, params: dict, scope_level: str,
                     scope_id: str, key: str | None = None, name: str | None = None, priority: int = 0,
                     locked: bool = False, effective_from: datetime | None = None,
                     effective_to: datetime | None = None) -> Rule:
        clean = templates.validate_params(family, template, params)
        if effective_to is not None and effective_to <= (effective_from or now()):
            raise RuleError("The end date must be after the start")
        templates.check_key(key)
        if scope_level not in templates.ALLOWED_LEVELS[family]:
            allowed = ", ".join(sorted(templates.ALLOWED_LEVELS[family], key=templates.LEVELS.index))
            raise RuleError(f"{family} rules can be set for: {allowed}")
        market_scope = await self.market_scope_for(scope_level, scope_id)
        r = Rule(
            rule_key=uuid.uuid4(), version=1, family=family, template=template, key=key,
            slot=templates.slot_for(family, template, key), name=name, params=clean,
            scope_level=scope_level, scope_id=scope_id, market_scope=market_scope, priority=priority,
            locked=locked, status="draft", effective_from=effective_from or now(), effective_to=effective_to, created_by=actor,
        )
        self.db.add(r)
        await self.db.flush()
        await audit.record(self.db, actor_id=actor, action="rule.created", entity_type="rule",
                           entity_id=r.rule_key, scope=market_scope, after=snapshot(r))
        return r

    async def update_draft(self, actor: uuid.UUID, rule_id: uuid.UUID, patch: dict[str, Any]) -> Rule:
        r = await self.get(rule_id)
        if r.status not in ("draft", "rejected"):
            raise RuleError("Only a draft can be changed; make a new version of a published rule")
        before = snapshot(r)
        if "params" in patch:
            r.params = templates.validate_params(r.family, r.template, patch.pop("params"))
        for k in ("name", "priority", "locked", "effective_from", "effective_to"):
            if k in patch:
                setattr(r, k, patch[k])
        if r.effective_to is not None and r.effective_to <= r.effective_from:
            raise RuleError("The end date must be after the start")
        r.status = "draft"
        await self.db.flush()
        await audit.record(self.db, actor_id=actor, action="rule.edited", entity_type="rule",
                           entity_id=r.rule_key, scope=r.market_scope, before=before, after=snapshot(r))
        return r

    async def new_version(self, actor: uuid.UUID, rule_id: uuid.UUID, *, params: dict | None = None,
                          effective_from: datetime | None = None, name: str | None = None,
                          from_version: Rule | None = None, action: str = "rule.version_created") -> Rule:
        base = from_version or await self.get(rule_id)
        versions = await self.versions(base.rule_key)
        if any(v.status in OPEN_STATUSES for v in versions):
            raise RuleError("This rule already has a draft or a version waiting for approval; finish that first")
        r = Rule(
            rule_key=base.rule_key, version=max(v.version for v in versions) + 1, family=base.family,
            template=base.template, key=base.key, slot=base.slot, name=name or base.name,
            params=templates.validate_params(base.family, base.template, params if params is not None else base.params),
            scope_level=base.scope_level, scope_id=base.scope_id, market_scope=base.market_scope,
            priority=base.priority, locked=base.locked, status="draft",
            effective_from=effective_from or now(), created_by=actor,
        )
        self.db.add(r)
        await self.db.flush()
        await audit.record(self.db, actor_id=actor, action=action, entity_type="rule", entity_id=r.rule_key,
                           scope=r.market_scope, before=snapshot(base), after=snapshot(r))
        return r

    async def discard(self, actor: uuid.UUID, rule_id: uuid.UUID) -> None:
        r = await self.get(rule_id)
        if r.status not in ("draft", "rejected"):
            raise RuleError("Only drafts can be discarded")
        before = snapshot(r)
        await self.db.delete(r)
        await self.db.flush()
        await audit.record(self.db, actor_id=actor, action="rule.discarded", entity_type="rule",
                           entity_id=before["rule_key"], scope=r.market_scope, before=before)

    # ── review and publish ───────────────────────────────────────────────────
    async def submit(self, actor: uuid.UUID, rule_id: uuid.UUID) -> Rule:
        """Money rules (and batching) wait for a second admin; other business rules publish now."""
        r = await self.get(rule_id)
        if r.status != "draft":
            raise RuleError("Only a draft can be sent for review")
        if templates.needs_approval(r.family, r.template):
            r.status = "pending_approval"
            self.db.add(RuleApproval(rule_id=r.id, requested_by=actor))
            await self.db.flush()
            await audit.record(self.db, actor_id=actor, action="rule.submitted", entity_type="rule",
                               entity_id=r.rule_key, scope=r.market_scope, after=snapshot(r))
            return r
        await self._publish(actor, r, "rule.published")
        return r

    async def approve(self, actor: uuid.UUID, rule_id: uuid.UUID, note: str | None = None) -> Rule:
        r = await self.get(rule_id)
        if r.status != "pending_approval":
            raise RuleError("This rule isn't waiting for approval")
        approval = (await self.approvals(r.id))[-1]
        if actor in (approval.requested_by, r.created_by):
            raise RuleError("A second admin must approve: you created or submitted this version")
        approval.decision, approval.decided_by, approval.decided_at, approval.note = "approved", actor, now(), note
        await self._publish(actor, r, "rule.approved", note=note)
        return r

    async def reject(self, actor: uuid.UUID, rule_id: uuid.UUID, note: str) -> Rule:
        r = await self.get(rule_id)
        if r.status != "pending_approval":
            raise RuleError("This rule isn't waiting for approval")
        approval = (await self.approvals(r.id))[-1]
        if actor == approval.requested_by:
            raise RuleError("Ask another admin to review it, or withdraw it by editing the draft")
        approval.decision, approval.decided_by, approval.decided_at, approval.note = "rejected", actor, now(), note
        before = snapshot(r)
        r.status = "rejected"
        await self.db.flush()
        await audit.record(self.db, actor_id=actor, action="rule.rejected", entity_type="rule", entity_id=r.rule_key,
                           scope=r.market_scope, before=before, after={**snapshot(r), "note": note})
        return r

    async def _publish(self, actor: uuid.UUID, r: Rule, action: str, note: str | None = None) -> None:
        before = snapshot(r)
        start = max(r.effective_from, now())
        r.status, r.effective_from = "published", start
        # Hand over: the version that was running stops when this one starts;
        # any version scheduled for later than this one is superseded.
        for other in await self.versions(r.rule_key):
            if other.id == r.id or other.status != "published":
                continue
            if other.effective_from >= start:
                other.effective_to = other.effective_from  # never runs
                other.status = "superseded"
            elif other.effective_to is None or other.effective_to > start:
                other.effective_to = start
        await self.db.flush()
        await audit.record(self.db, actor_id=actor, action=action, entity_type="rule", entity_id=r.rule_key,
                           scope=r.market_scope, before=before, after={**snapshot(r), **({"note": note} if note else {})})

    async def rollback(self, actor: uuid.UUID, version_id: uuid.UUID) -> Rule:
        """Bring back an earlier version: a new version with its settings,
        starting now. Money rules still need a second admin."""
        old = await self.get(version_id)
        if old.status not in ("published", "superseded"):
            raise RuleError("Only a version that was published can be brought back")
        r = await self.new_version(actor, old.id, params=old.params, from_version=old, action="rule.rolled_back")
        return await self.submit(actor, r.id)

    async def end(self, actor: uuid.UUID, rule_id: uuid.UUID, at: datetime | None = None) -> Rule:
        """Stop a published rule (e.g. end a promotion) at ``at`` or now."""
        r = await self.get(rule_id)
        if r.status != "published":
            raise RuleError("Only a published rule can be ended")
        stop = max(at or now(), now())
        before = snapshot(r)
        r.effective_to = stop if r.effective_to is None else min(r.effective_to, stop)
        await self.db.flush()
        await audit.record(self.db, actor_id=actor, action="rule.ended", entity_type="rule", entity_id=r.rule_key,
                           scope=r.market_scope, before=before, after=snapshot(r))
        return r

    # ── pause (B4) ───────────────────────────────────────────────────────────
    async def pause(self, actor: uuid.UUID, rule_id: uuid.UUID, reason: str) -> Rule:
        """Stop a kitchen's own offer for now without ending it: it stops
        applying at once and the kitchen sees why. Resume brings it back."""
        r = await self.get(rule_id)
        if r.family != "promotion" or r.scope_level != "restaurant" or r.params.get("funded_by") != "restaurant":
            raise RuleError("Only a kitchen's own offer can be paused; end other rules instead")
        if r.status != "published" or (r.effective_to is not None and r.effective_to <= now()):
            raise RuleError("Only a live offer can be paused")
        if r.paused_at is not None:
            raise RuleError("This offer is already paused")
        before = snapshot(r)
        r.paused_at, r.paused_by, r.paused_reason = now(), actor, reason.strip()
        await self.db.flush()
        await audit.record(self.db, actor_id=actor, action="offer.paused", entity_type="rule", entity_id=r.rule_key,
                           scope=r.market_scope, before=before, after=snapshot(r))
        return r

    async def resume(self, actor: uuid.UUID, rule_id: uuid.UUID) -> Rule:
        r = await self.get(rule_id)
        if r.paused_at is None:
            raise RuleError("This offer isn't paused")
        before = snapshot(r)
        r.paused_at = r.paused_by = r.paused_reason = None
        await self.db.flush()
        await audit.record(self.db, actor_id=actor, action="offer.resumed", entity_type="rule", entity_id=r.rule_key,
                           scope=r.market_scope, before=before, after=snapshot(r))
        return r

    # ── resolve ──────────────────────────────────────────────────────────────
    async def candidates(self, ctx: Context, at: datetime) -> list[Candidate]:
        pairs = ctx.scope_ids()
        conds = [(Rule.scope_level == lvl) & (Rule.scope_id == sid) for lvl, sid in pairs.items()]
        q = select(Rule).where(
            Rule.status == "published",
            Rule.paused_at.is_(None),  # B4: paused by an admin
            or_(*conds),
            Rule.effective_from <= at,
            or_(Rule.effective_to.is_(None), Rule.effective_to > at),
        )
        return [candidate(r) for r in (await self.db.execute(q)).scalars()]

    async def resolve(self, ctx: Context, at: datetime | None = None,
                      overlay_ids: list[uuid.UUID] = ()) -> dict[str, Candidate]:
        """The rules that apply at ``at``. ``overlay_ids``: drafts to try as if
        they were live (the price simulator compares live vs draft)."""
        at = at or now()
        overlay = []
        for rid in overlay_ids:
            r = await self.get(rid)
            c = candidate(r)
            overlay.append(Candidate(**{**c.__dict__, "status": "published", "effective_from": at, "effective_to": None}))
        return resolve(await self.candidates(ctx, at), ctx, at, overlay)

    async def count(self) -> int:
        return int((await self.db.execute(select(func.count()).select_from(Rule))).scalar() or 0)
