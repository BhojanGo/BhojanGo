import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.events import publish_payment_event
from app.db.base import get_db
from app.repositories.payment import PaymentRepository, WalletRepository
from app.schemas.payment import (
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
from app.services import razorpay_svc, stripe_svc

router = APIRouter(prefix="/payments", tags=["Payments"])
logger = structlog.get_logger(__name__)


@router.post("/initiate", response_model=PaymentInitiateResponse, status_code=status.HTTP_201_CREATED)
async def initiate_payment(
    data: PaymentInitiateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
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

    # Route by country
    if data.country == "US":
        result = await stripe_svc.create_payment_intent(
            amount=data.amount,
            currency=data.currency,
            order_id=str(data.order_id),
            idempotency_key=idempotency_key,
            payment_method_id=data.payment_method_id,
        )
        provider = "stripe"
        meta = {"client_secret": result["client_secret"]}
    else:
        result = await razorpay_svc.create_order(
            amount=data.amount,
            currency=data.currency,
            order_id=str(data.order_id),
            idempotency_key=idempotency_key,
        )
        provider = "razorpay"
        meta = {"razorpay_order_id": result["razorpay_order_id"]}

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


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    """Stripe webhook handler. Verifies signature and processes payment events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = await stripe_svc.process_webhook(payload, sig_header)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    repo = PaymentRepository(db)
    intent = await repo.get_by_provider_id(event["provider_payment_id"])
    if not intent:
        logger.warning("stripe_webhook_intent_not_found", provider_id=event["provider_payment_id"])
        return {"received": True}

    new_status = "succeeded" if event["status"] == "succeeded" else "failed"
    await repo.update_status(intent.id, new_status)

    if new_status == "succeeded":
        await publish_payment_event("payment.succeeded", {
            "payment_intent_id": str(intent.id),
            "order_id": str(intent.order_id),
            "user_id": str(intent.user_id),
            "amount": intent.amount,
            "currency": intent.currency,
            "provider": "stripe",
        })
    else:
        await publish_payment_event("payment.failed", {
            "payment_intent_id": str(intent.id),
            "order_id": str(intent.order_id),
            "user_id": str(intent.user_id),
            "failure_reason": event["event_type"],
            "provider": "stripe",
        })

    return {"received": True}


@router.post("/razorpay/webhook")
async def razorpay_webhook(request: Request, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    payload = await request.body()
    sig_header = request.headers.get("x-razorpay-signature", "")
    try:
        event = await razorpay_svc.process_webhook(payload, sig_header)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    repo = PaymentRepository(db)
    intent = await repo.get_by_provider_id(event["provider_payment_id"])
    if not intent:
        return {"received": True}

    new_status = "succeeded" if event["status"] == "succeeded" else "failed"
    await repo.update_status(intent.id, new_status)

    sns_event = "payment.succeeded" if new_status == "succeeded" else "payment.failed"
    await publish_payment_event(sns_event, {
        "payment_intent_id": str(intent.id),
        "order_id": str(intent.order_id),
        "user_id": str(intent.user_id),
        "amount": intent.amount,
        "currency": intent.currency,
        "provider": "razorpay",
    })
    return {"received": True}


@router.get("/{order_id}", response_model=PaymentResponse)
async def get_payment(
    order_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
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
    db: Annotated[AsyncSession, Depends(get_db)],
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
    elif intent.provider == "stripe":
        result = await stripe_svc.create_refund(
            intent.provider_payment_id, refund_amount, idempotency_key=data.idempotency_key
        )
        refund_id, refund_status = result["refund_id"], result["status"]
    else:
        result = await razorpay_svc.create_refund(intent.provider_payment_id, refund_amount)
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
    db: Annotated[AsyncSession, Depends(get_db)],
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
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WalletBalanceResponse:
    wallet_repo = WalletRepository(db)
    wallet = await wallet_repo.get_or_create(current_user.id, currency="INR" if current_user.country == "IN" else "USD")
    return WalletBalanceResponse.model_validate(wallet)


@wallet_router.get("/transactions", response_model=WalletTransactionListResponse)
async def get_wallet_transactions(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
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
