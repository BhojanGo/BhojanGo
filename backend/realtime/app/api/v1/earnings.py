"""Driver earnings protection + shift time tracking endpoints."""
import time
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import CurrentUser, get_current_user
from app.schemas.earnings import (
    EarningsBreakdownResponse,
    EarningsEstimateRequest,
    ShiftActivityRequest,
    ShiftStatusResponse,
)
from app.services import shifts
from app.services.earnings import calculate_earnings

router = APIRouter(prefix="/drivers/me", tags=["Driver Earnings"])
logger = structlog.get_logger(__name__)


def _require_driver(user: CurrentUser) -> None:
    if user.role not in ("driver", "admin", "super_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Driver access required")


@router.post("/shift/start", response_model=ShiftStatusResponse)
async def start_shift(current_user: Annotated[CurrentUser, Depends(get_current_user)]) -> ShiftStatusResponse:
    """Driver goes online — begins available-time tracking."""
    _require_driver(current_user)
    return ShiftStatusResponse(**await shifts.start_shift(current_user.user_id, time.time()))


@router.post("/shift/activity", response_model=ShiftStatusResponse)
async def set_shift_activity(
    data: ShiftActivityRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ShiftStatusResponse:
    """Switch between active (on delivery) and waiting/idle so the two are tracked separately."""
    _require_driver(current_user)
    try:
        return ShiftStatusResponse(**await shifts.set_activity(current_user.user_id, data.status, time.time()))
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active shift")


@router.get("/shift", response_model=ShiftStatusResponse)
async def shift_status(current_user: Annotated[CurrentUser, Depends(get_current_user)]) -> ShiftStatusResponse:
    _require_driver(current_user)
    return ShiftStatusResponse(**await shifts.get_shift(current_user.user_id, time.time()))


@router.post("/shift/end", response_model=ShiftStatusResponse)
async def end_shift(current_user: Annotated[CurrentUser, Depends(get_current_user)]) -> ShiftStatusResponse:
    """Driver goes offline — finalizes the shift and returns the totals."""
    _require_driver(current_user)
    return ShiftStatusResponse(**await shifts.end_shift(current_user.user_id, time.time()))


@router.post("/earnings/estimate", response_model=EarningsBreakdownResponse)
async def estimate_earnings(
    data: EarningsEstimateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> EarningsBreakdownResponse:
    """Compute a full earnings breakdown (floor pay, mileage, waiting, tips, batch bonus, net)."""
    _require_driver(current_user)
    result = calculate_earnings(
        available_minutes=data.available_minutes,
        active_minutes=data.active_minutes,
        waiting_minutes=data.waiting_minutes,
        miles=data.miles,
        tips=data.tips,
        deductions=data.deductions,
        num_orders=data.num_orders,
    )
    return EarningsBreakdownResponse(**result.to_dict())
