"""Internal: the batch engine (worker) hands realtime what it found (task 43).

Not for apps: every request is signed with INTERNAL_SERVICE_SECRET
(shared/internal_auth.py). Shadow suggestions are stored for the dispatch view;
live batches are offered to a rider if every order is still waiting and its
city has live batching on (realtime checks; the worker's view may be stale).
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.services import dispatch
from shared import internal_auth

router = APIRouter(prefix="/internal/dispatch", tags=["Internal"], include_in_schema=False)


async def signed(request: Request) -> None:
    try:
        internal_auth.verify(request.method, request.url.path, await request.body(),
                             request.headers.get("x-internal-timestamp"), request.headers.get("x-internal-signature"))
    except internal_auth.InternalAuthError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Internal endpoint")


class Batch(BaseModel):
    orders: list[str] = Field(min_length=2, max_length=3)  # drop-off order; the first is the lead
    score: int
    savings_percent: float
    total_distance_km: float
    total_time_min: float
    max_detour_min: float


class Batches(BaseModel):
    mode: Literal["shadow", "live"]
    city: str
    batches: list[Batch] = Field(max_length=100)


@router.post("/batches", dependencies=[Depends(signed)])
async def batches(data: Batches) -> dict:
    offered = 0
    for b in data.batches:
        meta = {**b.model_dump(), "city": data.city}
        if data.mode == "shadow":
            await dispatch.record_shadow(meta)
        elif await dispatch.offer_batch(b.orders, meta):
            offered += 1
    return {"received": len(data.batches), "offered": offered}
