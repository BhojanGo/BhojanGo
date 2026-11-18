"""Finance API (P13): payout runs, statements, payee accounts, reconciliation.

  finance.view     runs, statements, reconciliation (the admin's countries)
  finance.edit     create a run
  payouts.approve  approve and pay a run (not the admin who created it)
  payees           their own statements and payout account (set-up state, a fresh Stripe link)
  payee set-up     finance, or partners.* (the kitchen's city) / riders.* (the delivery partner's country):
                   see a payee's payout set-up, copy or send them a link (R10)
  webhooks         Stripe Connect (accounts) and Stripe (transfers): finance/service/connect.py
"""
import csv
import io
import uuid
from datetime import date
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.finance.models import PayoutAccount, PayoutRun, PayoutStatement
from core_api.modules.finance.service import connect, payouts
from core_api.modules.finance.service.payouts import FinanceError
from core_api.modules.finance.service.providers import ConnectSetupError, PayoutError
from core_api.modules.identity.api.dependencies import AdminContext, get_admin, require_permission
from core_api.modules.orders.api.dependencies import CurrentUser, get_current_user
from shared import authz
from shared.db import get_db
from shared.providers import ProviderConfigError

router = APIRouter(prefix="/finance", tags=["Finance"])
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
User = Annotated[CurrentUser, Depends(get_current_user)]


class RunCreate(BaseModel):
    country: str = Field(pattern=r"^[A-Z]{2}$")
    period_start: date = Field(description="Local date, included")
    period_end: date = Field(description="Local date, not included (a week: Monday to the next Monday)")


class AccountCreate(BaseModel):
    payee_type: Literal["restaurant", "rider"]
    restaurant_id: uuid.UUID | None = None


class AdminLink(BaseModel):
    send: bool = Field(False, description="Also send the link to the payee (push, email and the app's inbox)")


def _bad(e: FinanceError) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail={"code": "FINANCE_RULE", "message": str(e)})


def _provider_failed(e: PayoutError) -> HTTPException:
    """The payout provider refused or didn't answer. Connect not set up on the platform
    account is the admins' to fix (the message says where); the rest: try again."""
    if isinstance(e, ConnectSetupError):
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail={"code": "CONNECT_NOT_SET_UP", "message": str(e)})
    return HTTPException(status.HTTP_502_BAD_GATEWAY, detail={"code": "PAYOUT_PROVIDER_ERROR", "message": str(e)})


def run_out(r: PayoutRun) -> dict:
    return {"id": str(r.id), "country": r.country, "currency": r.currency, "period_start": r.period_start.isoformat(),
            "period_end": r.period_end.isoformat(), "status": r.status, "totals": r.totals,
            "created_by": str(r.created_by), "approved_by": str(r.approved_by) if r.approved_by else None,
            "paid_at": r.paid_at.isoformat() if r.paid_at else None}


def statement_out(s: PayoutStatement, with_lines: bool = True) -> dict:
    out = {"id": str(s.id), "run_id": str(s.run_id), "payee_type": s.payee_type, "payee_id": str(s.payee_id),
           "payee_name": s.payee_name, "currency": s.currency, "amount": s.amount, "summary": s.summary,
           "status": s.status, "transfer_id": s.transfer_id, "error": s.error, "attempts": s.attempts,
           "transferred_at": s.transferred_at.isoformat() if s.transferred_at else None}
    if with_lines:
        out["lines"] = s.lines
    return out


async def _run(db: AsyncSession, run_id: uuid.UUID) -> PayoutRun:
    r = await db.get(PayoutRun, run_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Payout run not found")
    return r


@router.post("/payout-runs", status_code=status.HTTP_201_CREATED)
async def create_run(data: RunCreate, admin: Annotated[AdminContext, Depends(require_permission("finance.edit"))], db: DB) -> dict:
    """Prepare payouts for a period: a statement per restaurant and rider."""
    admin.require("finance.edit", data.country)
    try:
        run = await payouts.create_run(db, admin.user.id, data.country, data.period_start, data.period_end)
    except FinanceError as e:
        raise _bad(e)
    return run_out(run)


@router.get("/payout-preview/restaurants/{restaurant_id}")
async def payout_preview(
    restaurant_id: uuid.UUID, admin: Annotated[AdminContext, Depends(require_permission("finance.view"))], db: DB,
    country: str = Query(pattern=r"^[A-Z]{2}$"), start: date = Query(...), end: date = Query(...),
) -> dict:
    """What a payout run for this period would pay the restaurant, line by line, without
    making the run (the same statement code)."""
    admin.require("finance.view", country)
    try:
        return await payouts.preview_restaurant(db, country, start, end, restaurant_id)
    except FinanceError as e:
        raise _bad(e)


@router.get("/payout-weeks")
async def payout_weeks(admin: Annotated[AdminContext, Depends(require_permission("finance.view"))], db: DB,
                       country: str = Query(pattern=r"^[A-Z]{2}$")) -> dict:
    """The weeks a run may cover (R12): the last 8 that have ended, Monday to Sunday in the
    country's time zone, newest first; `end` is the next Monday (not included)."""
    admin.require("finance.view", country)
    try:
        c = await payouts._country(db, country)
    except FinanceError as e:
        raise _bad(e)
    today = payouts.local_today(ZoneInfo(c.timezone))
    return {"timezone": c.timezone, "today": today.isoformat(),
            "weeks": [{"start": a.isoformat(), "end": b.isoformat()} for a, b in payouts.ended_weeks(today)]}


@router.get("/payout-runs")
async def list_runs(admin: Annotated[AdminContext, Depends(require_permission("finance.view"))], db: DB,
                    country: str | None = None) -> list[dict]:
    rows = (await db.execute(select(PayoutRun).order_by(PayoutRun.period_start.desc()))).scalars().all()
    return [run_out(r) for r in rows if admin.can("finance.view", r.country) and (country is None or r.country == country)]


@router.get("/payout-runs/{run_id}")
async def get_run(run_id: uuid.UUID, admin: Annotated[AdminContext, Depends(require_permission("finance.view"))], db: DB) -> dict:
    run = await _run(db, run_id)
    admin.require("finance.view", run.country)
    stmts = (await db.execute(select(PayoutStatement).where(PayoutStatement.run_id == run_id)
                              .order_by(PayoutStatement.payee_type, PayoutStatement.payee_name))).scalars().all()
    # Each payee's payout set-up (R10), so finance sees who is waiting for onboarding.
    accounts = {(a.payee_type, a.payee_id): a for a in (await db.execute(select(PayoutAccount).where(
        PayoutAccount.country == run.country, PayoutAccount.payee_id.in_([s.payee_id for s in stmts])))).scalars()} if stmts else {}
    return {**run_out(run), "statements": [
        {**statement_out(s, with_lines=False), "payout_setup": connect.state(accounts.get((s.payee_type, s.payee_id)))}
        for s in stmts]}


@router.post("/payout-runs/{run_id}/approve")
async def approve(run_id: uuid.UUID, admin: Annotated[AdminContext, Depends(require_permission("payouts.approve"))], db: DB) -> dict:
    """Approve and pay. Must be a different admin from the one who prepared it."""
    run = await _run(db, run_id)
    admin.require("payouts.approve", run.country)
    try:
        run = await payouts.approve_and_pay(db, admin.user.id, run_id)
    except FinanceError as e:
        raise _bad(e)
    return await get_run(run.id, admin, db)


@router.post("/payout-runs/{run_id}/retry")
async def retry(run_id: uuid.UUID, admin: Annotated[AdminContext, Depends(require_permission("payouts.approve"))], db: DB) -> dict:
    """Pay statements that failed or were waiting for the payee's account."""
    run = await _run(db, run_id)
    admin.require("payouts.approve", run.country)
    try:
        await payouts.retry(db, admin.user.id, run_id)
    except FinanceError as e:
        raise _bad(e)
    return await get_run(run_id, admin, db)


async def _payee_ids(db: AsyncSession, user: CurrentUser) -> list[tuple[str, uuid.UUID]]:
    from core_api.modules.catalog.models.restaurant import Restaurant

    ids: list[tuple[str, uuid.UUID]] = [("rider", user.id)] if user.role == "driver" else []
    if user.role == "restaurant_owner":
        ids += [("restaurant", r) for (r,) in (await db.execute(select(Restaurant.id).where(Restaurant.owner_id == user.id))).all()]
    return ids


@router.get("/statements/me")
async def my_statements(user: User, db: DB) -> list[dict]:
    """A partner's statements for their restaurants, or a rider's own (newest first)."""
    payees = await _payee_ids(db, user)
    out = []
    for kind, pid in payees:
        rows = (await db.execute(select(PayoutStatement, PayoutRun).join(PayoutRun, PayoutRun.id == PayoutStatement.run_id).where(
            PayoutStatement.payee_type == kind, PayoutStatement.payee_id == pid)
            .order_by(PayoutRun.period_start.desc()))).all()
        out += [{**statement_out(s), "period_start": r.period_start.isoformat(), "period_end": r.period_end.isoformat(),
                 "run_status": r.status, "country": r.country} for s, r in rows]
    # Sent back or didn't go through: the date it is paid again (the country's next payout day; R12).
    days: dict[str, str] = {}
    for st in out:
        if st["status"] in ("reversed", "failed"):
            if st["country"] not in days:
                days[st["country"]] = (await payouts.next_payout_day(db, st["country"])).isoformat()
            st["repay_on"] = days[st["country"]]
    return out


@router.get("/earnings/me")
async def my_earnings(user: User, db: DB) -> dict:
    """A rider's week so far: what the next weekly payout will pay, by day, with
    the hourly-floor top-up (engaged time: from accepting an offer to drop-off)."""
    if user.role != "driver":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Delivery partners only")
    try:
        return await payouts.rider_week(db, user.id, user.country)
    except FinanceError as e:
        raise _bad(e)


@router.get("/statements/{statement_id}")
async def get_statement(statement_id: uuid.UUID, user: User, db: DB) -> dict:
    s = await db.get(PayoutStatement, statement_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Statement not found")
    run = await _run(db, s.run_id)
    mine = (s.payee_type, s.payee_id) in await _payee_ids(db, user)
    if not mine and not authz.can([authz.Assignment.parse(a) for a in user.admin], "finance.view", run.country):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Statement not found")
    return statement_out(s)


async def _payee(db: AsyncSession, kind: str, payee_id: uuid.UUID) -> tuple[uuid.UUID, str, str | None, dict]:
    """(payee id, country, city code or None, profile for the provider) of a kitchen or a delivery partner."""
    from core_api.modules.catalog.models.restaurant import Restaurant
    from core_api.modules.identity.models.user import User as UserRow
    from core_api.modules.identity.service.profile import user_profile

    if kind == "restaurant":
        r = await db.get(Restaurant, payee_id)
        if r is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Kitchen not found")
        owner = (await user_profile(db, r.owner_id)) or {}
        return r.id, r.country, None, {**owner, "name": r.name}
    u = await db.get(UserRow, payee_id)
    if u is None or u.role != "driver":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Delivery partner not found")
    return u.id, u.country, None, await user_profile(db, u.id) or {}


async def _account_for(db: AsyncSession, kind: str, payee_id: uuid.UUID, country: str) -> PayoutAccount | None:
    rows = (await db.execute(select(PayoutAccount).where(PayoutAccount.payee_type == kind, PayoutAccount.payee_id == payee_id,
                                                         PayoutAccount.country == country)
                             .order_by(PayoutAccount.created_at.desc()))).scalars().all()
    return next((a for a in rows if a.status == "active"), rows[0] if rows else None)


async def _setup(db: AsyncSession, kind: str, payee_id: uuid.UUID, country: str, refresh: bool) -> dict:
    """What the payout screens show: the country's provider and the payee's account."""
    from core_api.modules.finance.service.providers import NoPayoutProvider, country_payout_provider

    try:
        provider = await country_payout_provider(db, country)
        name, hosted = provider.name, provider.hosted_onboarding
    except (NoPayoutProvider, ProviderConfigError):
        name, hosted = None, False
    acct = await _account_for(db, kind, payee_id, country)
    if acct is not None and refresh and connect.state(acct) != "ready":
        await connect.sync(db, acct)
    return {"payee_type": kind, "payee_id": str(payee_id), "country": country, "provider": name,
            "hosted_onboarding": hosted, "state": connect.state(acct), "account": connect.account_out(acct)}


@router.post("/payout-accounts", status_code=status.HTTP_201_CREATED)
async def open_account(data: AccountCreate, user: User, db: DB) -> dict:
    """Set up where you're paid, with your country's payout provider in Markets
    (Stripe Connect Express, Razorpay Route). Opens the account once and reuses it;
    with Stripe, ``onboarding_url`` is a fresh link to Stripe's pages (bank, identity),
    null once payouts are enabled. 409 FINANCE_RULE when the country has no payout
    provider; 503 CONNECT_NOT_SET_UP when the platform's Stripe account can't open
    connected accounts yet; 502 when the provider fails."""
    from core_api.modules.catalog.models.restaurant import Restaurant

    if data.payee_type == "restaurant":
        r = await db.get(Restaurant, data.restaurant_id) if data.restaurant_id else None
        if r is None or r.owner_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
        payee_id = r.id
    else:
        if user.role != "driver":
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Delivery partners only")
        payee_id = user.id
    payee_id, country, _, profile = await _payee(db, data.payee_type, payee_id)
    try:
        acct, url = await payouts.open_account(db, data.payee_type, payee_id, country, profile)
    except FinanceError as e:  # the country has no payout provider in Markets
        raise _bad(e) from e
    except PayoutError as e:
        raise _provider_failed(e) from e
    return {"id": str(acct.id), "provider": acct.provider, "status": acct.status, "state": connect.state(acct),
            "onboarding_url": url, "account": connect.account_out(acct)}


@router.get("/payout-accounts/me")
async def my_accounts(user: User, db: DB, refresh: bool = Query(False, description="Ask the provider now (back from Stripe)")) -> list[dict]:
    """Your payout accounts with their set-up state (not_started, in_progress, action_needed, ready)."""
    out = []
    for kind, pid in await _payee_ids(db, user):
        for a in (await db.execute(select(PayoutAccount).where(PayoutAccount.payee_type == kind, PayoutAccount.payee_id == pid))).scalars():
            if refresh and connect.state(a) != "ready":
                await connect.sync(db, a)
            out.append(connect.account_out(a))
    return out


@router.get("/payout-accounts/me/setup")
async def my_setup(user: User, db: DB, payee_type: Literal["restaurant", "rider"] = Query(...),
                   restaurant_id: uuid.UUID | None = None, refresh: bool = False) -> dict:
    """The Payouts screen: your country's payout provider (stripe_connect, razorpay_route,
    fake; null when it has none yet), whether set-up happens on the provider's pages,
    and your account's state. ``refresh`` asks the provider first (back from Stripe)."""
    pid = restaurant_id if payee_type == "restaurant" else user.id
    if pid is None or (payee_type, pid) not in await _payee_ids(db, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    payee_id, country, _, _ = await _payee(db, payee_type, pid)
    return await _setup(db, payee_type, payee_id, country, refresh)


# ── admins: a payee's payout set-up, and a link to finish it (R10) ─────────────

def _admin_scope(admin: AdminContext, kind: str, country: str, city: str | None, edit: bool) -> None:
    """Finance for the country, or the people who look after the payee: partners
    (kitchens, their city) and riders (delivery partners, their country)."""
    need = ("finance.edit", "partners.edit" if kind == "restaurant" else "riders.edit") if edit \
        else ("finance.view", "partners.view" if kind == "restaurant" else "riders.view")
    if admin.can(need[0], country) or admin.can(need[1], city or country) or (kind == "rider" and authz.can_within(admin.assignments, need[1], country)):
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "FORBIDDEN_SCOPE", "message": f"You need {need[0]} or {need[1]} for {city or country}"})


async def _city_code(db: AsyncSession, payee_kind: str, payee_id: uuid.UUID) -> str | None:
    if payee_kind != "restaurant":
        return None
    from core_api.modules.catalog.models.restaurant import Restaurant
    from core_api.modules.catalog.service.access import scope_of

    r = await db.get(Restaurant, payee_id)
    return await scope_of(db, r) if r else None


@router.get("/payees/{kind}/{target_id}/payout-account")
async def payee_setup(kind: Literal["restaurant", "rider"], target_id: uuid.UUID,
                      admin: Annotated[AdminContext, Depends(get_admin)], db: DB, refresh: bool = False) -> dict:
    """A kitchen's or delivery partner's payout set-up (finance.view for the country, or
    partners.view for the kitchen's city / riders.view for the delivery partner's country)."""
    payee_id, country, _, _ = await _payee(db, kind, target_id)
    _admin_scope(admin, kind, country, await _city_code(db, kind, payee_id), edit=False)
    return await _setup(db, kind, payee_id, country, refresh)


@router.post("/payees/{kind}/{target_id}/payout-account/link")
async def payee_link(kind: Literal["restaurant", "rider"], target_id: uuid.UUID, data: AdminLink,
                     admin: Annotated[AdminContext, Depends(get_admin)], db: DB) -> dict:
    """A link for the payee to set up payouts on the provider's pages (opens the account
    if there isn't one). It works for 7 days and makes a fresh Stripe link each time it
    is opened. ``send`` also sends it to them. null when the provider has no hosted
    set-up or the account is already ready."""
    from shared import outbox

    payee_id, country, city, profile = await _payee(db, kind, target_id)
    _admin_scope(admin, kind, country, await _city_code(db, kind, payee_id), edit=True)
    try:
        acct, url = await payouts.open_account(db, kind, payee_id, country, profile)
    except FinanceError as e:
        raise _bad(e) from e
    except PayoutError as e:
        raise _provider_failed(e) from e
    link = connect.kept_link(acct) if url else None
    sent = False
    if link and data.send:
        await outbox.add(db, "payout.setup_link", kind, payee_id, {
            "payee_type": kind, "payee_id": str(payee_id), "link": link, "provider": acct.provider, "user_id": None}, "finance")
        sent = True
    from core_api.modules.audit import service as audit

    await audit.record(db, actor_id=admin.user.id, action="payout_account.link", entity_type="payout_account", entity_id=acct.id,
                       scope=country, after={"payee_type": kind, "sent": sent})
    return {"link": link, "expires_in_days": connect.LINK_DAYS if link else None, "sent": sent,
            **(await _setup(db, kind, payee_id, country, False))}


@router.get("/payout-onboarding", response_class=RedirectResponse, status_code=status.HTTP_302_FOUND)
async def payout_onboarding(db: DB, t: str = Query(..., max_length=200)) -> RedirectResponse:
    """The link people keep (and Stripe's refresh_url): checks the signed token and
    redirects to a fresh Stripe onboarding page, or to the website's /payouts/done page
    (already set up, link expired, or Stripe unavailable)."""
    from shared.config import get_settings

    web = get_settings().identity.PUBLIC_WEB_URL.rstrip("/") + connect.WEB_PAGE
    acct_id = connect.read_token(t)
    acct = await db.get(PayoutAccount, acct_id) if acct_id else None
    if acct is None:
        return RedirectResponse(f"{web}?status=expired", status.HTTP_302_FOUND)
    app = connect.APP_OF.get(acct.payee_type, "kitchen")
    try:
        if connect.state(acct) != "ready":
            await connect.sync(db, acct)
        url = await connect.fresh_link(acct)
    except PayoutError:
        return RedirectResponse(f"{web}?app={app}&status=unavailable", status.HTTP_302_FOUND)
    return RedirectResponse(url or f"{web}?app={app}", status.HTTP_302_FOUND)


# ── Stripe webhooks for payouts (R10) ─────────────────────────────────────────

async def _stripe_event(request: Request, db: AsyncSession, secret: str) -> dict:
    import json

    import stripe

    payload = await request.body()
    try:
        stripe.Webhook.construct_event(payload, request.headers.get("stripe-signature", ""), secret)
    except Exception:  # noqa: BLE001 - a bad signature, an empty secret or a body that isn't JSON
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid signature")
    event = json.loads(payload)
    return {"received": True, "result": await connect.apply_event(db, event)}


@router.post("/stripe/connect/webhook")
async def stripe_connect_webhook(request: Request, db: DB) -> dict:
    """Connect endpoint (events on connected accounts): account.updated,
    account.application.deauthorized, payout.failed, payout.paid. Signed with
    STRIPE_CONNECT_WEBHOOK_SECRET (else STRIPE_WEBHOOK_SECRET); each event applied once."""
    from shared.config import get_settings

    p = get_settings().payments
    return await _stripe_event(request, db, p.STRIPE_CONNECT_WEBHOOK_SECRET or p.STRIPE_WEBHOOK_SECRET)


@router.post("/stripe/webhook")
async def stripe_payouts_webhook(request: Request, db: DB) -> dict:
    """Account endpoint for payouts: transfer.created, transfer.updated, transfer.reversed
    (a reversed transfer shows as reversed; retry pays it again). Signed with
    STRIPE_PAYOUTS_WEBHOOK_SECRET (else STRIPE_WEBHOOK_SECRET); each event applied once."""
    from shared.config import get_settings

    p = get_settings().payments
    return await _stripe_event(request, db, p.STRIPE_PAYOUTS_WEBHOOK_SECRET or p.STRIPE_WEBHOOK_SECRET)


@router.get("/contribution")
async def contribution(
    admin: Annotated[AdminContext, Depends(require_permission("finance.view"))], db: DB,
    scope: str = Query(pattern=r"^[A-Z]{2}(-[A-Z0-9]{1,3}(-[A-Z0-9]{2,5})?)?$"), start: date = Query(...), end: date = Query(...),
) -> dict:
    """Contribution per order, by city: what the platform keeps after payment fees, rider
    pay (tips excluded), platform-funded offers and the refunds it pays."""
    from core_api.modules.finance.service.contribution import contribution as build

    admin.require("finance.view", scope)
    try:
        return await build(db, scope, start, end)
    except FinanceError as e:
        raise _bad(e)


@router.get("/reconciliation", response_model=None)
async def reconciliation(
    admin: Annotated[AdminContext, Depends(require_permission("finance.view"))], db: DB,
    country: str = Query(pattern=r"^[A-Z]{2}$"), start: date = Query(...), end: date = Query(...),
    format: Literal["json", "csv"] = "json",
) -> dict | PlainTextResponse:
    """Captured vs refunded vs owed (tax, restaurants, riders, platform), by
    provider, with every order that doesn't line up. CSV for spreadsheets."""
    admin.require("finance.view", country)
    try:
        report = await payouts.reconciliation(db, country, start, end)
    except FinanceError as e:
        raise _bad(e)
    if format == "json":
        return report
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["section", "key", "value"])
    for section in ("orders", "money"):
        for k, v in report[section].items():
            w.writerow([section, k, v])
    for provider, vals in report["by_provider"].items():
        for k, v in vals.items():
            w.writerow([f"provider:{provider}", k, v])
    for issue in report["issues"]:
        w.writerow(["issue", issue["issue"], issue["order_id"]])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename=reconciliation-{country}-{start}-{end}.csv"})
