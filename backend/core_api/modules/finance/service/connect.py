"""Payout onboarding and transfer status (R10): Stripe Connect Express for countries
whose Markets payout provider is stripe_connect; the same shapes for the others.

An account's *state* is what kitchen partners, delivery partners and admins see:

    not_started    no payout account yet
    in_progress    opened; the payee hasn't finished Stripe's pages, or Stripe is checking them
    action_needed  Stripe needs more (requirements due, account disabled, a bank payout failed)
    ready          payouts enabled: the weekly run pays this account

Account Links last minutes and work once, so we never hand out a Stripe URL that
must survive: the link people keep (the refresh_url Stripe sends them back to, and
the link admins copy) is ours, ``/api/v1/finance/payout-onboarding?t=<token>``,
which makes a fresh Account Link and redirects to it. The return_url is the
website's /payouts/done page, which sends them back to the app.

Webhooks (``apply_event``), each event applied once (processed_webhook_events):

    Connect endpoint  account.updated, account.application.deauthorized, payout.failed, payout.paid
    Account endpoint  transfer.created, transfer.updated, transfer.reversed
"""
import base64
import hashlib
import hmac
import time
import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.finance.models import PayoutAccount, PayoutRun, PayoutStatement
from core_api.modules.finance.service.providers import PayoutError, provider_by_name
from shared.config import get_settings

logger = structlog.get_logger(__name__)

STATES = ("not_started", "in_progress", "action_needed", "ready")
LINK_DAYS = 7  # how long a link we hand out (refresh_url, an admin's copy) keeps working
WEB_PAGE = "/payouts/done"  # apps/web: "You're set up with Stripe", and the way back to the app
APP_OF = {"restaurant": "kitchen", "rider": "delivery"}


# ── state ─────────────────────────────────────────────────────────────────────

def state(acct: PayoutAccount | None) -> str:
    if acct is None:
        return "not_started"
    if acct.payout_error or (acct.status == "restricted" and (acct.disabled_reason or "").startswith(("rejected", "deauthorized"))):
        return "action_needed"
    if acct.payouts_enabled:
        return "ready"
    if not acct.details_submitted:
        return "in_progress"
    waiting = acct.disabled_reason in (None, "", "requirements.pending_verification", "under_review")
    return "in_progress" if waiting and not acct.requirements_due else "action_needed"


def account_out(acct: PayoutAccount | None) -> dict | None:
    if acct is None:
        return None
    return {"id": str(acct.id), "payee_type": acct.payee_type, "payee_id": str(acct.payee_id), "provider": acct.provider,
            "status": acct.status, "country": acct.country, "state": state(acct),
            "details_submitted": acct.details_submitted, "payouts_enabled": acct.payouts_enabled,
            "requirements_due": list(acct.requirements_due or []), "disabled_reason": acct.disabled_reason,
            "payout_error": acct.payout_error,
            "updated_at": acct.updated_at.isoformat() if acct.updated_at else None}


def apply_account(acct: PayoutAccount, obj: dict) -> bool:
    """Copy a Stripe account object (account.updated, Account.retrieve) onto ours.
    Returns True when it became ready just now."""
    was_ready = state(acct) == "ready"
    req = obj.get("requirements") or {}
    due = list(dict.fromkeys([*(req.get("past_due") or []), *(req.get("currently_due") or [])]))
    acct.details_submitted = bool(obj.get("details_submitted"))
    acct.payouts_enabled = bool(obj.get("payouts_enabled"))
    acct.requirements_due = due
    acct.disabled_reason = req.get("disabled_reason") or None
    acct.status = "active" if acct.payouts_enabled else ("restricted" if acct.disabled_reason and acct.details_submitted else "pending")
    acct.updated_at = datetime.now(UTC)
    return not was_ready and state(acct) == "ready"


def mark_created(acct: PayoutAccount) -> None:
    """A new account: the fake is active at once; others wait for the provider."""
    acct.payouts_enabled = acct.details_submitted = acct.status == "active"


# ── links ─────────────────────────────────────────────────────────────────────

def _key() -> bytes:
    return hashlib.sha256(b"payout-onboarding:" + get_settings().INTERNAL_SERVICE_SECRET.encode()).digest()


def make_token(account_id: uuid.UUID, days: int = LINK_DAYS, now: float | None = None) -> str:
    exp = int((now or time.time()) + days * 86400)
    body = f"{account_id.hex}.{exp}"
    sig = base64.urlsafe_b64encode(hmac.new(_key(), body.encode(), hashlib.sha256).digest()[:18]).decode().rstrip("=")
    return f"{body}.{sig}"


def read_token(token: str, now: float | None = None) -> uuid.UUID | None:
    """The payout account a token is for; None when forged or expired."""
    try:
        acct_hex, exp, sig = token.split(".")
        want = base64.urlsafe_b64encode(hmac.new(_key(), f"{acct_hex}.{exp}".encode(), hashlib.sha256).digest()[:18]).decode().rstrip("=")
        if not hmac.compare_digest(sig, want) or int(exp) < (now or time.time()):
            return None
        return uuid.UUID(hex=acct_hex)
    except (ValueError, TypeError):
        return None


def kept_link(acct: PayoutAccount) -> str:
    """The link that lasts LINK_DAYS: ours, which makes a fresh Account Link each time."""
    api = get_settings().payments.PUBLIC_API_URL.rstrip("/")
    return f"{api}/api/v1/finance/payout-onboarding?t={make_token(acct.id)}"


def return_url(acct: PayoutAccount) -> str:
    web = get_settings().identity.PUBLIC_WEB_URL.rstrip("/")
    return f"{web}{WEB_PAGE}?app={APP_OF.get(acct.payee_type, 'kitchen')}"


async def fresh_link(acct: PayoutAccount) -> str | None:
    """A new Account Link (Stripe), or None for providers without hosted onboarding."""
    provider = provider_by_name(acct.provider)
    if not getattr(provider, "hosted_onboarding", False) or acct.payouts_enabled:
        return None
    return await provider.onboarding_link(acct.external_id, kept_link(acct), return_url(acct))  # type: ignore[attr-defined]


async def sync(db: AsyncSession, acct: PayoutAccount) -> PayoutAccount:
    """Ask the provider now (when the payee comes back from Stripe, or an admin looks).
    A provider error keeps what we had: the webhook will catch up."""
    provider = provider_by_name(acct.provider)
    if not hasattr(provider, "account_state"):
        return acct
    try:
        obj = await provider.account_state(acct.external_id)  # type: ignore[attr-defined]
    except PayoutError as e:
        logger.warning("payout_account_sync_failed", account=acct.external_id, error=str(e))
        return acct
    if apply_account(acct, obj):
        await pay_waiting(db, acct)
    await db.flush()
    return acct


# ── paying what waited for onboarding ─────────────────────────────────────────

async def pay_waiting(db: AsyncSession, acct: PayoutAccount) -> int:
    """The payee just became ready: pay their statements in approved runs that were
    waiting for them (no_account / onboarding). Returns how many runs were paid."""
    from core_api.modules.finance.service.payouts import pay_pending

    runs = (await db.execute(
        select(PayoutRun).join(PayoutStatement, PayoutStatement.run_id == PayoutRun.id).where(
            PayoutStatement.payee_type == acct.payee_type, PayoutStatement.payee_id == acct.payee_id,
            PayoutStatement.status.in_(("no_account", "onboarding")), PayoutRun.country == acct.country,
            PayoutRun.status.in_(("approved", "partially_paid"))).distinct())).scalars().all()
    provider = provider_by_name(acct.provider)
    for run in runs:
        await pay_pending(db, run, provider, payee=(acct.payee_type, acct.payee_id))
        logger.info("payout_paid_after_onboarding", run_id=str(run.id), payee_type=acct.payee_type, payee_id=str(acct.payee_id))
    return len(runs)


# ── webhooks ──────────────────────────────────────────────────────────────────

async def _account(db: AsyncSession, external_id: str | None) -> PayoutAccount | None:
    if not external_id:
        return None
    return (await db.execute(select(PayoutAccount).where(PayoutAccount.external_id == external_id))).scalars().first()


async def _statement(db: AsyncSession, transfer: dict) -> PayoutStatement | None:
    st = (await db.execute(select(PayoutStatement).where(PayoutStatement.transfer_id == transfer.get("id")))).scalars().first()
    if st is None and (sid := (transfer.get("metadata") or {}).get("payout_statement_id")):
        try:
            st = await db.get(PayoutStatement, uuid.UUID(sid))
        except ValueError:
            return None
    return st


async def apply_event(db: AsyncSession, event: dict) -> str:
    """Apply one verified Stripe event to accounts and statements. Returns what it did."""
    from core_api.modules.payments.models.payment import ProcessedWebhookEvent

    if await db.get(ProcessedWebhookEvent, ("stripe_connect", event["id"])) is not None:
        return "already_processed"
    kind, obj = event["type"], event["data"]["object"]
    did = "ignored"
    if kind == "account.updated":
        acct = await _account(db, obj.get("id"))
        if acct is not None:
            did = "account_updated"
            if apply_account(acct, obj):
                await db.flush()
                await pay_waiting(db, acct)
                did = "account_ready"
    elif kind == "account.application.deauthorized":
        acct = await _account(db, event.get("account"))
        if acct is not None:
            acct.payouts_enabled, acct.status, acct.disabled_reason = False, "restricted", "deauthorized"
            did = "account_deauthorized"
    elif kind in ("payout.failed", "payout.paid"):
        acct = await _account(db, event.get("account"))
        if acct is not None:
            acct.payout_error = (obj.get("failure_message") or obj.get("failure_code") or "The bank payout failed") if kind == "payout.failed" else None
            did = "bank_payout_failed" if kind == "payout.failed" else "bank_payout_paid"
    elif kind.startswith("transfer."):
        st = await _statement(db, obj)
        if st is not None:
            reversed_all = bool(obj.get("reversed")) or int(obj.get("amount_reversed") or 0) >= int(obj.get("amount") or 1)
            if kind in ("transfer.reversed", "transfer.updated") and reversed_all and st.status == "paid":
                st.status, st.error = "reversed", "The transfer was reversed in Stripe; retry pays it again"
                st.attempts += 1  # a retry must be a new transfer, not this one again
                run = await db.get(PayoutRun, st.run_id)
                if run is not None and run.status == "paid":
                    run.status, run.paid_at = "partially_paid", None  # finance sees it and retries
                did = "transfer_reversed"
            elif int(obj.get("amount_reversed") or 0) > 0 and st.status == "paid":
                st.error = f"Partly reversed in Stripe ({obj.get('amount_reversed')} of {obj.get('amount')})"
                did = "transfer_partly_reversed"
            elif kind == "transfer.created" and st.transfer_id is None:
                st.transfer_id, st.status, st.error = obj["id"], "paid", None
                did = "transfer_recorded"
    db.add(ProcessedWebhookEvent(provider="stripe_connect", event_id=event["id"]))
    await db.flush()
    logger.info("stripe_connect_event", event_type=kind, event_id=event["id"], result=did)
    return did
