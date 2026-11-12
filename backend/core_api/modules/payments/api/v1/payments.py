import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.payments.api.dependencies import CurrentUser, get_current_user
from shared import outbox
from shared.db import get_db
from core_api.modules.payments.repository.payment import PaymentRepository, WalletRepository
from core_api.modules.payments.schemas.payment import (
    ItemRefundRequest,
    RazorpayVerifyRequest,
    FakeCompleteRequest,
    PaymentInitiateRequest,
    PaymentInitiateResponse,
    PaymentResponse,
    RefundRequest,
    RefundResponse,
    WalletBalanceResponse,
    WalletTopupRequest,
    WalletTransactionListResponse,
    WalletTransactionResponse,
)
from core_api.modules.identity.api.dependencies import AdminContext, require_permission
from core_api.modules.payments.service.gateways import (
    verify_razorpay_checkout,
    fake_webhook_body,
    gateway_by_name,
    get_gateway,
    sign_fake,
)
from shared.config import get_settings

router = APIRouter(prefix="/payments", tags=["Payments"])
logger = structlog.get_logger(__name__)


@router.post("/initiate", response_model=PaymentInitiateResponse, status_code=status.HTTP_201_CREATED)
async def initiate_payment(
    data: PaymentInitiateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> PaymentInitiateResponse:
    """Pay for an order waiting for payment. The amount and currency are the
    order's (its quoted total), never the client's; the gateway follows the
    order's country (Razorpay in India, Stripe in the US). Calling it again
    returns the same open payment; after a failure it starts a new one."""
    from core_api.modules.orders.service.lookup import order_for_payment

    order = await order_for_payment(db, data.order_id, current_user.id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order["status"] != "pending_payment":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail={"code": "ORDER_NOT_PAYABLE", "message": f"This order is {order['status'].replace('_', ' ')}"})
    amount, currency, country = order["amount_minor"], order["currency"], order["country"]
    if (data.amount is not None and data.amount != amount) or (data.currency is not None and data.currency != currency):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail={"code": "AMOUNT_MISMATCH", "message": "The amount doesn't match the order"})

    repo = PaymentRepository(db)
    attempts = await repo.list_by_order_id(data.order_id)
    open_intent = next((i for i in attempts if i.status in ("pending", "processing", "succeeded")), None)
    if open_intent:
        return PaymentInitiateResponse(
            payment_intent_id=str(open_intent.id), provider=open_intent.provider,  # type: ignore[arg-type]
            client_secret=open_intent.metadata_.get("client_secret"),
            razorpay_order_id=open_intent.metadata_.get("razorpay_order_id"),
            amount=open_intent.amount, currency=open_intent.currency,  # type: ignore[arg-type]
            checkout=_with_ids(open_intent.metadata_.get("checkout"), open_intent.id),
        )
    idempotency_key = f"{data.order_id}:attempt-{len(attempts) + 1}"

    if data.payment_method_type == "wallet":
        wallet_repo = WalletRepository(db)
        await wallet_repo.debit(current_user.id, amount=Decimal(amount) / 100, description=f"Order payment {data.order_id}",
                                reference_id=str(data.order_id), reference_type="order")
        intent = await repo.create_intent(
            order_id=data.order_id, user_id=current_user.id, provider="wallet", provider_payment_id=idempotency_key,
            amount=amount, currency=currency, status="pending", idempotency_key=idempotency_key,
            metadata_={"payment_method": "wallet"},
        )
        await apply_payment_event(db, "wallet", {"event_type": "payment.succeeded", "provider_payment_id": idempotency_key,
                                                 "status": "succeeded", "event_id": f"wallet:{intent.id}"})
        return PaymentInitiateResponse(payment_intent_id=str(intent.id), provider="wallet", amount=amount, currency=currency)

    gateway = get_gateway(country)
    customer = await _checkout_customer(db, gateway, current_user.id, country)
    result = await gateway.create(
        amount=amount, currency=currency, order_id=str(data.order_id), idempotency_key=idempotency_key,
        payment_method_id=data.payment_method_id, customer=customer,
    )
    meta = {k: v for k, v in result.items() if k in ("client_secret", "razorpay_order_id", "fake_outcome", "checkout")}
    intent = await repo.create_intent(
        order_id=data.order_id, user_id=current_user.id, provider=gateway.name,
        provider_payment_id=result["provider_payment_id"], amount=amount, currency=currency, status="pending",
        idempotency_key=idempotency_key, metadata_=meta,
    )
    return PaymentInitiateResponse(
        payment_intent_id=str(intent.id), provider=gateway.name,  # type: ignore[arg-type]
        client_secret=meta.get("client_secret"), razorpay_order_id=meta.get("razorpay_order_id"),
        amount=amount, currency=currency, checkout=_with_ids(meta.get("checkout"), intent.id),
    )


def _with_ids(checkout: dict | None, intent_id) -> dict | None:  # type: ignore[no-untyped-def]
    if checkout and "complete_path" in checkout:
        checkout = {**checkout, "complete_path": checkout["complete_path"].format(payment_intent_id=intent_id)}
    return checkout


async def _checkout_customer(db: AsyncSession, gateway, user_id: uuid.UUID, country: str) -> dict:  # type: ignore[no-untyped-def]
    """Who is paying (prefill) and how they may pay in this country (markets)."""
    from core_api.modules.identity.service.profile import user_profile
    from core_api.modules.markets.service.markets import MarketService
    from core_api.modules.payments.models.payment import PaymentCustomer

    profile = await user_profile(db, user_id) or {"user_id": str(user_id)}
    c = await MarketService(db).repo.country(country)
    methods = list((c.settings or {}).get("payment_methods", [])) if c else []
    row = await db.get(PaymentCustomer, (user_id, gateway.name))
    customer_id = await gateway.ensure_customer(profile, row.customer_id if row else None)
    if customer_id and row is None:
        db.add(PaymentCustomer(user_id=user_id, provider=gateway.name, customer_id=customer_id))
        await db.flush()
    return {**profile, "provider_customer_id": customer_id, "methods": methods}


async def _handle_webhook(gateway_name: str, request: Request, db: AsyncSession) -> dict:
    """Verify, then apply a payment webhook. Idempotent: a repeated or late
    event for a payment that already has that outcome changes nothing and
    publishes nothing."""
    gateway = gateway_by_name(gateway_name)
    payload = await request.body()
    try:
        event = await gateway.parse_webhook(payload, request.headers.get(gateway.signature_header, ""))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return await apply_payment_event(db, gateway_name, event)


async def apply_payment_event(db: AsyncSession, gateway_name: str, event: dict) -> dict:
    if event["status"] not in ("succeeded", "failed"):
        return {"received": True}
    if event.get("event_id") and not await _first_delivery(db, gateway_name, event["event_id"]):
        logger.info("webhook_event_already_processed", provider=gateway_name, event_id=event["event_id"])
        return {"received": True, "duplicate": True}
    repo = PaymentRepository(db)
    intent = await repo.get_by_provider_id(event["provider_payment_id"], for_update=True)
    if not intent:
        logger.warning("webhook_intent_not_found", provider=gateway_name, provider_id=event["provider_payment_id"])
        return {"received": True}

    new_status = event["status"]
    if intent.status == new_status or intent.status in ("refunded", "partially_refunded"):
        logger.info("webhook_duplicate_ignored", provider=gateway_name, intent_id=str(intent.id), status=intent.status)
        return {"received": True, "duplicate": True}
    if intent.status == "succeeded" and new_status == "failed":
        # A late failure never undoes a captured payment.
        logger.warning("webhook_late_failure_ignored", provider=gateway_name, intent_id=str(intent.id))
        return {"received": True, "duplicate": True}

    await repo.update_status(intent.id, new_status)
    if event.get("razorpay_payment_id"):
        intent.metadata_ = {**intent.metadata_, "razorpay_payment_id": event["razorpay_payment_id"]}

    base = {
        "payment_intent_id": str(intent.id),
        "order_id": str(intent.order_id),
        "user_id": str(intent.user_id),
        "amount": intent.amount,
        "currency": intent.currency,
        "provider": gateway_name,
    }
    if new_status == "succeeded":
        await outbox.add(db, "payment.succeeded", "order", intent.order_id, base, "payment-svc")
        from core_api.modules.orders.service.order import OrderService

        await OrderService(db).on_payment_succeeded(intent.order_id)  # same transaction: paid <=> placed
        await _record_tax_transaction(db, intent)
    else:
        intent.metadata_ = {**intent.metadata_, "failure_reason": event.get("failure_reason") or event["event_type"]}
        await outbox.add(db, "payment.failed", "order", intent.order_id,
                         {**base, "failure_reason": event["event_type"]}, "payment-svc")
        from core_api.modules.orders.service.order import OrderService

        await OrderService(db).on_payment_failed(intent.order_id)
    return {"received": True}


async def _record_tax_transaction(db: AsyncSession, intent) -> None:  # type: ignore[no-untyped-def]
    """US: turn the order's Stripe Tax calculation into a tax transaction (what
    Stripe reports and files). Best effort: a failure is logged for finance."""
    from core_api.modules.payments.service.tax import record_tax_transaction
    from core_api.modules.pricing.service.quotes import QuoteService

    snap = await QuoteService(db).snapshot(intent.order_id)
    calc = (snap.context or {}).get("tax_calculation") if snap else None
    if not calc:
        return
    tx = await record_tax_transaction(calc["provider"], calc["calculation_id"], str(intent.order_id))
    if tx:
        intent.metadata_ = {**intent.metadata_, "tax_transaction": tx}


async def _first_delivery(db: AsyncSession, provider: str, event_id: str) -> bool:
    """Record the event id; False if we have seen it (a redelivery)."""
    from sqlalchemy import text

    row = (await db.execute(text(
        "INSERT INTO processed_webhook_events (provider, event_id) VALUES (:p, :e) "
        "ON CONFLICT DO NOTHING RETURNING event_id"), {"p": provider, "e": event_id})).first()
    return row is not None


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request, db: Annotated[AsyncSession, Depends(get_db, scope="function")]) -> dict:
    """Stripe webhook. Verifies the signature, then applies the event."""
    return await _handle_webhook("stripe", request, db)


@router.post("/razorpay/webhook")
async def razorpay_webhook(request: Request, db: Annotated[AsyncSession, Depends(get_db, scope="function")]) -> dict:
    return await _handle_webhook("razorpay", request, db)


@router.post("/fake/webhook", include_in_schema=False)
async def fake_webhook(request: Request, db: Annotated[AsyncSession, Depends(get_db, scope="function")]) -> dict:
    """Webhooks from the local fake gateway (refused in production)."""
    if get_settings().is_production:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return await _handle_webhook("fake", request, db)


@router.post("/fake/{payment_intent_id}/complete")
async def complete_fake_payment(
    payment_intent_id: uuid.UUID,
    data: FakeCompleteRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> dict:
    """Local only: finish a fake payment as if the customer paid (or the card
    was declined). Sends the same signed webhook a real gateway would."""
    if get_settings().is_production:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    intent = await PaymentRepository(db).get_by_id(payment_intent_id)
    if not intent or intent.provider != "fake" or str(intent.user_id) != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fake payment not found")
    outcome = data.outcome or intent.metadata_.get("fake_outcome", "succeeded")
    body = fake_webhook_body(intent.provider_payment_id, outcome)
    gateway = gateway_by_name("fake")
    event = await gateway.parse_webhook(body, sign_fake(body))
    result = await apply_payment_event(db, "fake", event)
    return {**result, "outcome": outcome}


@router.get("/{order_id}", response_model=PaymentResponse)
async def get_payment(
    order_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> PaymentResponse:
    repo = PaymentRepository(db)
    intent = await repo.get_by_order_id(order_id)
    if not intent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return PaymentResponse.model_validate(intent)


@router.post("/razorpay/verify")
async def razorpay_verify(
    data: RazorpayVerifyRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> dict:
    """The app calls this with what Razorpay Checkout returned. A valid signature
    captures the payment now; the webhook that follows is a duplicate."""
    if not verify_razorpay_checkout(data.razorpay_order_id, data.razorpay_payment_id, data.razorpay_signature):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Razorpay signature")
    intent = await PaymentRepository(db).get_by_provider_id(data.razorpay_order_id)
    if intent is None or intent.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return await apply_payment_event(db, "razorpay", {
        "event_type": "payment.captured", "provider_payment_id": data.razorpay_order_id, "status": "succeeded",
        "razorpay_payment_id": data.razorpay_payment_id, "event_id": f"{data.razorpay_payment_id}:captured"})


@router.get("/orders/{order_id}/status")
async def payment_status(
    order_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> dict:
    """For the "payment didn't go through" screen: what happened, whether the
    customer can try again, and until when the order's price is held."""
    from core_api.modules.orders.service.lookup import order_for_payment

    order = await order_for_payment(db, order_id, current_user.id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    attempts = await PaymentRepository(db).list_by_order_id(order_id)
    last = attempts[-1] if attempts else None
    return {
        "order_id": str(order_id), "order_status": order["status"],
        "amount": order["amount_minor"], "currency": order["currency"],
        "payment_status": last.status if last else "not_started",
        "failure_reason": last.metadata_.get("failure_reason") if last else None,
        "attempts": len(attempts),
        "can_retry": order["status"] == "pending_payment" and (last is None or last.status == "failed"),
        "price_held_until": order["payment_due_at"],
    }


@router.post("/orders/{order_id}/refunds", status_code=status.HTTP_201_CREATED)
async def refund_by_item(
    order_id: uuid.UUID,
    data: ItemRefundRequest,
    admin: Annotated[AdminContext, Depends(require_permission("refunds.issue"))],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> dict:
    """Refund items (each with its share of discounts and its tax), and/or the
    delivery fee. Support agents are limited per order (business rule)."""
    from core_api.modules.orders.service.lookup import order_market
    from core_api.modules.payments.service import refunds

    city = await order_market(db, order_id)
    if city is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    admin.require("refunds.issue", city or "*")
    try:
        r = await refunds.refund_items(
            db, order_id=order_id, requests=[refunds.ItemRequest(str(i.menu_item_id), i.quantity) for i in data.items],
            include_delivery=data.include_delivery_fee, reason=data.reason, note=data.note,
            actor_id=admin.user.id, assignments=admin.assignments)
    except refunds.RefundError as e:
        code = status.HTTP_403_FORBIDDEN if "refund limit" in str(e) else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=code, detail={"code": "REFUND_REFUSED", "message": str(e)})
    return _refund_out(r)


@router.get("/orders/{order_id}/refunds")
async def list_order_refunds(
    order_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> list[dict]:
    """The order's refunds: for its customer, or an admin who can view it."""
    from core_api.modules.orders.service.lookup import order_customer, order_market
    from core_api.modules.payments.service.refunds import list_refunds
    from shared import authz

    owner = await order_customer(db, order_id)
    city = await order_market(db, order_id)
    allowed = owner == current_user.id or (city and authz.can(
        [authz.Assignment.parse(a) for a in current_user.admin], "orders.view", city))
    if owner is None or not allowed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return [_refund_out(r) for r in await list_refunds(db, order_id)]


def _refund_out(r) -> dict:  # type: ignore[no-untyped-def]
    return {"id": str(r.id), "order_id": str(r.order_id), "amount": r.amount, "currency": r.currency, "kind": r.kind,
            "reason": r.reason, "fault": r.fault, "note": r.note, "lines": r.lines, "status": r.status,
            "provider_refund_id": r.provider_refund_id, "created_at": r.created_at.isoformat() if r.created_at else None}


# ── Wallet routes ─────────────────────────────────────────────────────────────
wallet_router = APIRouter(prefix="/wallet", tags=["Wallet"])


@wallet_router.post("/topup", response_model=WalletBalanceResponse)
async def topup_wallet(
    data: WalletTopupRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> WalletBalanceResponse:
    wallet_repo = WalletRepository(db)
    wallet, _ = await wallet_repo.credit(
        current_user.id,
        amount=data.amount,
        description=f"Wallet top-up via {data.payment_method_id}",
        reference_id=data.payment_method_id,
        reference_type="topup",
    )
    return WalletBalanceResponse.model_validate(wallet)


@wallet_router.get("/balance", response_model=WalletBalanceResponse)
async def get_wallet_balance(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> WalletBalanceResponse:
    wallet_repo = WalletRepository(db)
    wallet = await wallet_repo.get_or_create(current_user.id, currency="INR" if current_user.country == "IN" else "USD")
    return WalletBalanceResponse.model_validate(wallet)


@wallet_router.get("/transactions", response_model=WalletTransactionListResponse)
async def get_wallet_transactions(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> WalletTransactionListResponse:
    wallet_repo = WalletRepository(db)
    txns, total = await wallet_repo.list_transactions(current_user.id, page=page, limit=limit)
    return WalletTransactionListResponse(
        items=[WalletTransactionResponse.model_validate(t) for t in txns],
        total=total,
        page=page,
        limit=limit,
    )
