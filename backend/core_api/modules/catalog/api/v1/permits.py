"""R39: the US food permit (catalog/service/permits.py): the restaurant sends it, an admin reviews it."""
import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.catalog.api.dependencies import CurrentUser, get_current_user
from core_api.modules.catalog.models.restaurant import Restaurant
from core_api.modules.catalog.service import access
from core_api.modules.catalog.service import permits as svc
from shared import authz
from shared.db import get_db

router = APIRouter(prefix="/restaurants", tags=["Food permit"])
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
User = Annotated[CurrentUser, Depends(get_current_user)]


class PermitIn(BaseModel):
    number: str = Field(min_length=3, max_length=40, description="As printed on the permit")
    expires_on: date
    # The permit, uploaded first with POST /uploads (purpose partner_document)
    document_key: str | None = Field(default=None, max_length=300)


class ReviewIn(BaseModel):
    decision: Literal["approve", "reject"]
    note: str | None = Field(default=None, max_length=300, description="Why it is turned down (the restaurant sees it)")


def _bad(e: svc.PermitError) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": "FOOD_PERMIT", "message": str(e)})


@router.get("/admin/permits")
async def permits_to_review(user: User, db: DB, state: Literal["pending", "all"] = "pending",
                            country: str | None = Query(None, pattern=r"^[A-Z]{2}$")) -> list[dict]:
    """Admin (partners.view): food permits waiting for review (new restaurants and renewals), in your cities."""
    if not authz.scopes_with(access.assignments(user), "partners.view"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admins only")
    q = select(Restaurant).where(Restaurant.deleted_at.is_(None), Restaurant.food_permit_number.is_not(None))
    if state == "pending":
        q = q.where(Restaurant.food_permit_status == "pending")
    if country:
        q = q.where(Restaurant.country == country)
    rows = (await db.execute(q.order_by(Restaurant.food_permit_expires_on).limit(200))).scalars().all()
    return [{**svc.out(r), "name": r.name, "city": r.city, "restaurant_status": r.status}
            for r in rows if await access.admin_may(db, user, r, "partners.view")]


@router.put("/{restaurant_id}/food-permit")
async def submit_permit(restaurant_id: uuid.UUID, data: PermitIn, user: User, db: DB) -> dict:
    """The restaurant's food permit (owner, or an admin with partners.edit). Waits for an admin's review."""
    r = await access.manage(db, user, restaurant_id)
    if data.document_key is not None and not data.document_key.startswith(f"partner_document/{user.id}/"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail={"code": "FILE_NOT_YOURS", "message": "Upload the permit first (POST /uploads)"})
    try:
        r = await svc.submit(db, r, data.number, data.expires_on, data.document_key, datetime.now(UTC).date())
    except svc.PermitError as e:
        raise _bad(e)
    return svc.out(r, await svc.required(db, r.country))


@router.get("/{restaurant_id}/food-permit")
async def get_permit(restaurant_id: uuid.UUID, user: User, db: DB) -> dict:
    r = await access.manage(db, user, restaurant_id, "partners.view")
    return svc.out(r, await svc.required(db, r.country))


@router.post("/{restaurant_id}/food-permit/review")
async def review_permit(restaurant_id: uuid.UUID, data: ReviewIn, user: User, db: DB) -> dict:
    """Admin (partners.edit in the restaurant's city): approve the permit, or turn it down with a reason."""
    from core_api.modules.audit import service as audit

    r = await access.administer(db, user, restaurant_id)
    try:
        r = await svc.review(db, r, data.decision == "approve", user.id, data.note, datetime.now(UTC).date())
    except svc.PermitError as e:
        raise _bad(e)
    await audit.record(db, actor_id=user.id, action="food_permit.approved" if data.decision == "approve" else "food_permit.rejected", entity_type="restaurant", entity_id=r.id,
                       scope=await access.scope_of(db, r), after={"number": r.food_permit_number,
                                                                    "expires_on": str(r.food_permit_expires_on), "note": data.note})
    return svc.out(r, await svc.required(db, r.country))
