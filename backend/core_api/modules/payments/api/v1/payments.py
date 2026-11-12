import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.payments.api.dependencies import CurrentUser, get_current_user
from core_api.modules.payments.service.events import publish_payment_event
from shared.db import get_db
from core_api.modules.payments.repository.payment import PaymentRepository, WalletRepository
from core_api.modules.payments.schemas.payment import (
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
from core_api.modules.payments.service.gateways import (
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
    """Initiate payment — routes to Stripe (US) or Razorpay (IN) based on country."""
    repo = PaymentRepository(db)

    # Idempotency key: order_id + user_id + amount
    idempotency_key = f"{data.order_id}:{current_user.user_id}:{data.amount}"

    # Check for existing intent (idempotency)
    existing = await repo.get_by_idempotency_key(idempotency_key)
    if existing and existing.status in ("pending", "processing", "succeeded"):
        return PaymentInitiateResponse(
            payment_intent_id=str(existing.id),
            provider=existing.provider,  # type: ignore[arg-type]
            client_secret=existing.metadata_.get("client_secret"),
            razorpay_order_id=existing.metadata_.get("razorpay_order_id"),
            amount=existing.amount,
            currency=existing.currency,  # type: ignore[arg-type]
        )

    if data.payment_method_type == "wallet":
        # Deduct from wallet directly
        wallet_repo = WalletRepository(db)
        _, _ = await wallet_repo.debit(
            current_user.id,
            amount=Decimal(data.amount) / 100,  # cents/paise -> major units
            description=f"Order payment {data.order_id}",
            reference_id=str(data.order_id),
            reference_type="order",
        )
        intent = await repo.create_intent(
            order_id=data.order_id,
            user_id=current_user.id,
            provider="wallet",
            provider_payment_id=idempotency_key,
            amount=data.amount,
            currency=data.currency,
            status="succeeded",
            idempotency_key=idempotency_key,
            metadata_={"payment_method": "wallet"},
        )
        await publish_payment_event("payment.succeeded", {
            "payment_intent_id": str(intent.id),
            "order_id": str(data.order_id),
            "user_id": current_user.user_id,
            "amount": data.amount,
            "currency": data.currency,
            "provider": "wallet",
        })
        return PaymentInitiateResponse(
            payment_intent_id=str(intent.id),
            provider="wallet",
            amount=data.amount,
            currency=data.currency,
        )

    gateway = get_gateway(data.country)
    result = await gateway.create(
        amount=data.amount,
        currency=data.currency,
        order_id=str(data.order_id),
        idempotency_key=idempotency_key,
        payment_method_id=data.payment_method_id,
    )
    provider = gateway.name
    meta = {k: v for k, v in result.items() if k in ("client_secret", "razorpay_order_id", "fake_outcome")}

    intent = await repo.create_intent(
        order_id=data.order_id,
        user_id=current_user.id,
        provider=provider,
        provider_payment_id=result["provider_payment_id"],
        amount=data.amount,
        currency=data.currency,
        status="pending",
        idempotency_key=idempotency_key,
        metadata_=meta,
    )

    return PaymentInitiateResponse(
        payment_intent_id=str(intent.id),
        provider=provider,  # type: ignore[arg-type]
        client_secret=meta.get("client_secret"),
        razorpay_order_id=meta.get("razorpay_order_id"),
        amount=data.amount,
        currency=data.currency,
    )


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
        await publish_payment_event("payment.succeeded", base)
    else:
        await publish_payment_event("payment.failed", {**base, "failure_reason": event["event_type"]})
    return {"received": True}


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


@router.post("/{order_id}/refund", response_model=RefundResponse)
async def refund_payment(
    order_id: uuid.UUID,
    data: RefundRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> RefundResponse:
    if current_user.role not in ("admin", "super_admin", "customer"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    repo = PaymentRepository(db)
    intent = await repo.get_by_order_id(order_id)
    if not intent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No payment found for this order")

    # Idempotency: a retry with the same key returns the original refund without re-charging.
    # Checked before the refundable-status gate so a retried *full* refund still replays.
    refunds_log: list[dict] = list(intent.metadata_.get("refunds", []))
    if data.idempotency_key:
        for record in refunds_log:
            if record.get("idempotency_key") == data.idempotency_key:
                return RefundResponse(
                    refund_id=record["refund_id"],
                    order_id=str(order_id),
                    amount=record["amount"],
                    currency=intent.currency,
                    status=record["status"],  # type: ignore[arg-type]
                    refund_to=record["refund_to"],
                    created_at=record["created_at"],
                )

    if intent.status not in ("succeeded", "partially_refunded"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment is not in a refundable state")

    # Cap: cannot refund more than what remains on the original payment.
    already_refunded = intent.refunded_amount or 0
    remaining = intent.amount - already_refunded
    if remaining <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment has already been fully refunded")

    refund_amount = data.amount or remaining
    if refund_amount > remaining:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Refund amount {refund_amount} exceeds remaining refundable amount {remaining}",
        )

    if data.refund_to == "wallet":
        wallet_repo = WalletRepository(db)
        await wallet_repo.credit(
            current_user.id,
            amount=Decimal(refund_amount) / 100,  # cents/paise -> major units
            description=f"Refund for order {order_id}",
            reference_id=str(order_id),
            reference_type="refund",
        )
        refund_id = f"wallet_refund_{uuid.uuid4()}"
        refund_status = "succeeded"
    else:
        result = await gateway_by_name(intent.provider).refund(
            intent.provider_payment_id, refund_amount, data.idempotency_key, intent.metadata_
        )
        refund_id, refund_status = result["refund_id"], result["status"]

    created_at = datetime.now(UTC).isoformat()

    # Persist refund state on the loaded intent (committed by the get_db dependency).
    new_refunded_total = already_refunded + refund_amount
    intent.refunded_amount = new_refunded_total
    intent.status = "refunded" if new_refunded_total >= intent.amount else "partially_refunded"
    refunds_log.append({
        "idempotency_key": data.idempotency_key,
        "refund_id": refund_id,
        "amount": refund_amount,
        "status": refund_status,
        "refund_to": data.refund_to,
        "reason": data.reason,
        "created_at": created_at,
    })
    # Reassign metadata_ so SQLAlchemy detects the JSONB mutation.
    intent.metadata_ = {**intent.metadata_, "refunds": refunds_log}

    return RefundResponse(
        refund_id=refund_id,
        order_id=str(order_id),
        amount=refund_amount,
        currency=intent.currency,
        status=refund_status,  # type: ignore[arg-type]
        refund_to=data.refund_to,
        created_at=created_at,
    )


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
