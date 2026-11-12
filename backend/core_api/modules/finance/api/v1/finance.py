"""Finance API (P13): payout runs, statements, payee accounts, reconciliation.

  finance.view     runs, statements, reconciliation (the admin's countries)
  finance.edit     create a run
  payouts.approve  approve and pay a run (not the admin who created it)
  payees           their own statements and payout account
"""
import csv
import io
import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.finance.models import PayoutAccount, PayoutRun, PayoutStatement
from core_api.modules.finance.service import payouts
from core_api.modules.finance.service.payouts import FinanceError
from core_api.modules.identity.api.dependencies import AdminContext, require_permission
from core_api.modules.orders.api.dependencies import CurrentUser, get_current_user
from shared import authz
from shared.db import get_db

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
    return_url: str = "https://bhojango.example/payouts/done"


def _bad(e: FinanceError) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail={"code": "FINANCE_RULE", "message": str(e)})


def run_out(r: PayoutRun) -> dict:
    return {"id": str(r.id), "country": r.country, "currency": r.currency, "period_start": r.period_start.isoformat(),
            "period_end": r.period_end.isoformat(), "status": r.status, "totals": r.totals,
            "created_by": str(r.created_by), "approved_by": str(r.approved_by) if r.approved_by else None,
            "paid_at": r.paid_at.isoformat() if r.paid_at else None}


def statement_out(s: PayoutStatement, with_lines: bool = True) -> dict:
    out = {"id": str(s.id), "run_id": str(s.run_id), "payee_type": s.payee_type, "payee_id": str(s.payee_id),
           "payee_name": s.payee_name, "currency": s.currency, "amount": s.amount, "summary": s.summary,
           "status": s.status, "transfer_id": s.transfer_id, "error": s.error}
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
    return {**run_out(run), "statements": [statement_out(s, with_lines=False) for s in stmts]}


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
                 "run_status": r.status} for s, r in rows]
    return out


@router.get("/earnings/me")
async def my_earnings(user: User, db: DB) -> dict:
    """A rider's week so far: what the next weekly payout will pay, by day, with
    the hourly-floor top-up (engaged time: from accepting an offer to drop-off)."""
    if user.role != "driver":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Riders only")
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


@router.post("/payout-accounts", status_code=status.HTTP_201_CREATED)
async def open_account(data: AccountCreate, user: User, db: DB) -> dict:
    """Set up where you're paid: Stripe Connect Express (US) or Razorpay Route
    (India). Follow onboarding_url to finish (bank, identity)."""
    from core_api.modules.catalog.models.restaurant import Restaurant
    from core_api.modules.identity.service.profile import user_profile

    profile = await user_profile(db, user.id) or {}
    if data.payee_type == "restaurant":
        r = await db.get(Restaurant, data.restaurant_id) if data.restaurant_id else None
        if r is None or r.owner_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
        payee_id, country, profile = r.id, r.country, {**profile, "name": r.name}
    else:
        if user.role != "driver":
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Riders only")
        payee_id, country = user.id, user.country
    acct, url = await payouts.open_account(db, data.payee_type, payee_id, country, profile, data.return_url)
    return {"id": str(acct.id), "provider": acct.provider, "status": acct.status, "onboarding_url": url}


@router.get("/payout-accounts/me")
async def my_accounts(user: User, db: DB) -> list[dict]:
    out = []
    for kind, pid in await _payee_ids(db, user):
        rows = (await db.execute(select(PayoutAccount).where(PayoutAccount.payee_type == kind, PayoutAccount.payee_id == pid))).scalars()
        out += [{"id": str(a.id), "payee_type": a.payee_type, "payee_id": str(a.payee_id), "provider": a.provider,
                 "status": a.status, "country": a.country} for a in rows]
    return out


@router.post("/stripe/connect/webhook")
async def stripe_connect_webhook(request: Request, db: DB) -> dict:
    """account.updated from Stripe Connect: active once payouts are enabled."""
    import stripe

    from shared.config import get_settings

    try:
        event = stripe.Webhook.construct_event(await request.body(), request.headers.get("stripe-signature", ""),
                                               get_settings().payments.STRIPE_WEBHOOK_SECRET)
    except Exception:  # noqa: BLE001
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid signature")
    if event["type"] == "account.updated":
        acct = event["data"]["object"]
        await payouts.mark_account(db, acct["id"], bool(acct.get("payouts_enabled")))
    return {"received": True}


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
