"""Riders (P18): uploads, the onboarding checklist and documents.

A rider can go online once their phone is verified, their licence and vehicle
insurance are approved and the background check has cleared (admins review
them; realtime asks /internal/riders/{id}/ready before putting a rider online).
The payout account is on the checklist too, but pay waits for it rather than
blocking work (see finance: statements without an account wait as no_account).
"""
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.api.dependencies import AdminContext, require_permission
from core_api.modules.identity.models.rider import RiderDocument
from core_api.modules.identity.models.user import User
from core_api.modules.orders.api.dependencies import CurrentUser, get_current_user
from shared import authz, internal_auth
from shared.db import get_db
from shared.providers.storage import get_storage

router = APIRouter(tags=["Riders"])
internal = APIRouter(prefix="/internal/riders", tags=["Internal"], include_in_schema=False)
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]


def rider_only(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    """Refused before the body is read, so a non-rider never gets a validation error."""
    if user.role != "driver":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Riders only")
    return user


Me = Annotated[CurrentUser, Depends(rider_only)]

MAX_BYTES = 5 * 1024 * 1024
TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "application/pdf": "pdf"}
DOCUMENTS = ("licence", "insurance")  # what the rider uploads; the background check is ours
REQUIRED = ("identity", "licence", "insurance", "background_check")


# ── uploads ──────────────────────────────────────────────────────────────────

def uploader(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    """Riders (delivery photos, documents) and partners (FSSAI licence, P19)."""
    if user.role not in ("driver", "restaurant_owner"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Riders and partners only")
    return user


PURPOSES = {"delivery_proof": "driver", "rider_document": "driver", "partner_document": "restaurant_owner"}


@router.post("/uploads", status_code=status.HTTP_201_CREATED)
async def upload(user: Annotated[CurrentUser, Depends(uploader)], file: Annotated[UploadFile, File()],
                 purpose: Annotated[Literal["delivery_proof", "rider_document", "partner_document"], Form()]) -> dict:
    """A photo of the bags at the door, a rider's document, or a partner's licence
    (photo or PDF). Returns the key to send with it (files are private)."""
    if PURPOSES[purpose] != user.role:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "WRONG_PURPOSE", "message": "Not an upload you can make"})
    ctype = (file.content_type or "").split(";")[0]
    if ctype not in TYPES or (purpose == "delivery_proof" and not ctype.startswith("image/")):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            detail={"code": "FILE_TYPE", "message": "Send a JPEG, PNG or WebP photo (or a PDF for documents)"})
    data = await file.read(MAX_BYTES + 1)
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": "FILE_EMPTY", "message": "The file is empty"})
    if len(data) > MAX_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail={"code": "FILE_TOO_LARGE", "message": "Files can be up to 5 MB"})
    key = f"{purpose}/{user.user_id}/{uuid.uuid4()}.{TYPES[ctype]}"
    await get_storage().put(key, data, ctype)
    return {"key": key, "content_type": ctype, "size": len(data)}


# ── onboarding ───────────────────────────────────────────────────────────────

class StepOut(BaseModel):
    key: str
    title: str
    status: Literal["done", "in_review", "needed", "waiting", "rejected"]
    detail: str
    required: bool


class OnboardingOut(BaseModel):
    first_name: str
    country: str
    done: int
    total: int
    ready: bool
    steps: list[StepOut]


class DocumentIn(BaseModel):
    kind: Literal["licence", "insurance"]
    file_key: str = Field(max_length=300)


def _labels(country: str) -> dict[str, tuple[str, str]]:
    """Title and what we need, by country."""
    if country == "IN":
        return {"identity": ("Phone and identity", ""), "licence": ("Driving licence", "Photo of the front of your licence"),
                "payout": ("Bank account for payouts", "Where we send your weekly pay"),
                "insurance": ("Vehicle RC and insurance", "Photo of your insurance certificate"),
                "background_check": ("Background check", "Starts after insurance · usually 2–5 days")}
    return {"identity": ("Phone and identity", ""), "licence": ("Driver's licence", "Photo of the front of your licence"),
            "payout": ("Payout account", "Where we send your weekly pay"),
            "insurance": ("Vehicle insurance", "Photo of your card"),
            "background_check": ("Background check", "Starts after insurance · usually 2–5 days")}


async def onboarding(db: AsyncSession, rider_id: uuid.UUID) -> OnboardingOut:
    from core_api.modules.finance.models import PayoutAccount

    user = await db.get(User, rider_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Rider not found")
    docs = {d.kind: d for d in (await db.execute(select(RiderDocument).where(RiderDocument.rider_id == rider_id))).scalars()}
    accounts = (await db.execute(select(PayoutAccount).where(
        PayoutAccount.payee_type == "rider", PayoutAccount.payee_id == rider_id))).scalars().all()
    labels = _labels(user.country)
    steps: list[StepOut] = []

    def add(key: str, st: str, detail: str | None = None) -> None:
        title, need = labels[key]
        steps.append(StepOut(key=key, title=title, status=st, required=key in REQUIRED,  # type: ignore[arg-type]
                             detail=detail if detail is not None else ({"done": "Verified", "in_review": "We're checking it"}.get(st, need))))

    add("identity", "done" if user.is_phone_verified else "needed", None if user.is_phone_verified else "Verify your phone number")

    def doc_status(kind: str) -> tuple[str, str | None]:
        d = docs.get(kind)
        if d is None:
            return "needed", None
        if d.status == "approved":
            return "done", None
        if d.status == "rejected":
            return "rejected", d.note or "Please upload it again"
        return "in_review", None

    add("licence", *doc_status("licence"))
    if any(a.status == "active" for a in accounts):
        add("payout", "done", "Set up")
    else:
        add("payout", "in_review" if accounts else "needed", "Finish setting up with our payments partner" if accounts else None)
    ins, ins_note = doc_status("insurance")
    add("insurance", ins, f"Needed now · {labels['insurance'][1].lower()}" if ins == "needed" else ins_note)
    bg = docs.get("background_check")
    if bg is None:
        add("background_check", "waiting")
    elif bg.status == "approved":
        add("background_check", "done", "Cleared")
    elif bg.status == "rejected":
        add("background_check", "rejected", bg.note or "Contact rider support")
    else:
        add("background_check", "in_review", "In progress · usually 2–5 days")
    done = sum(1 for s in steps if s.status == "done")
    ready = all(s.status == "done" for s in steps if s.required)
    return OnboardingOut(first_name=(user.full_name or "").split(" ")[0], country=user.country, done=done,
                         total=len(steps), ready=ready, steps=steps)


@router.get("/riders/me/onboarding", response_model=OnboardingOut)
async def my_onboarding(user: Me, db: DB) -> OnboardingOut:
    return await onboarding(db, user.id)


@router.post("/riders/me/documents", response_model=OnboardingOut)
async def submit_document(data: DocumentIn, user: Me, db: DB) -> OnboardingOut:
    """Send an uploaded licence or insurance for review. When both are in, the
    background check starts."""
    if not data.file_key.startswith(f"rider_document/{user.user_id}/"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail={"code": "FILE_NOT_YOURS", "message": "Upload the document first (POST /uploads)"})
    docs = {d.kind: d for d in (await db.execute(select(RiderDocument).where(RiderDocument.rider_id == user.id))).scalars()}
    d = docs.get(data.kind)
    if d is not None and d.status == "approved":
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "ALREADY_APPROVED", "message": "This one is already approved"})
    if d is None:
        d = RiderDocument(rider_id=user.id, kind=data.kind)
        db.add(d)
        docs[data.kind] = d
    d.status, d.file_key, d.note, d.reviewed_by, d.reviewed_at = "submitted", data.file_key, None, None, None
    if all(k in docs for k in DOCUMENTS) and "background_check" not in docs:
        db.add(RiderDocument(rider_id=user.id, kind="background_check", status="submitted", updated_at=datetime.now(UTC)))
    await db.flush()
    return await onboarding(db, user.id)


# ── admin: review documents, view files (P21) ─────────────────────────────────

class DocumentOut(BaseModel):
    id: str
    rider_id: str
    rider_name: str
    rider_phone: str | None
    country: str
    kind: str
    status: str
    file_key: str | None
    note: str | None
    submitted_at: datetime


class ReviewIn(BaseModel):
    decision: Literal["approve", "reject"]
    note: str | None = Field(default=None, max_length=500)


@router.get("/riders/documents", response_model=list[DocumentOut])
async def documents(admin: Annotated[AdminContext, Depends(require_permission("riders.view"))], db: DB,
                    status_: Annotated[Literal["submitted", "approved", "rejected"], Query(alias="status")] = "submitted",
                    country: str | None = Query(None, pattern=r"^[A-Z]{2}$")) -> list[DocumentOut]:
    """Rider documents for review in the countries you can see (riders aren't tied to a city)."""
    q = select(RiderDocument, User).join(User, User.id == RiderDocument.rider_id).where(RiderDocument.status == status_)
    if country:
        q = q.where(User.country == country)
    rows = (await db.execute(q.order_by(RiderDocument.updated_at))).all()
    return [DocumentOut(id=str(d.id), rider_id=str(u.id), rider_name=u.full_name, rider_phone=u.phone, country=u.country, kind=d.kind,
                        status=d.status, file_key=d.file_key, note=d.note, submitted_at=d.updated_at)
            for d, u in rows if authz.can_within(admin.assignments, "riders.view", u.country)]


@router.post("/riders/documents/{document_id}/review", response_model=DocumentOut)
async def review(document_id: uuid.UUID, data: ReviewIn, admin: Annotated[AdminContext, Depends(require_permission("riders.edit"))],
                 db: DB) -> DocumentOut:
    """Approve or reject a rider's document. The rider can go online once the
    licence, insurance and background check are all approved."""
    d = await db.get(RiderDocument, document_id)
    u = await db.get(User, d.rider_id) if d else None
    if d is None or u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found")
    admin.require("riders.edit", u.country, within=True)
    if data.decision == "reject" and not data.note:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": "NOTE_REQUIRED", "message": "Tell the rider what to fix"})
    d.status = "approved" if data.decision == "approve" else "rejected"
    d.note, d.reviewed_by, d.reviewed_at = data.note, admin.user.id, datetime.now(UTC)
    from core_api.modules.audit import service as audit

    await audit.record(db, actor_id=admin.user.id, action=f"rider_document.{d.status}", entity_type="rider_document", entity_id=d.id,
                       scope=u.country, after={"kind": d.kind, "note": d.note})
    await db.flush()
    await db.refresh(d)  # updated_at is set by the database
    return DocumentOut(id=str(d.id), rider_id=str(u.id), rider_name=u.full_name, rider_phone=u.phone, country=u.country, kind=d.kind,
                       status=d.status, file_key=d.file_key, note=d.note, submitted_at=d.updated_at)


@router.get("/uploads/view")
async def view_upload(key: Annotated[str, Query(max_length=300)], admin: Annotated[AdminContext, Depends(require_permission("partners.view"))],
                      db: DB) -> Response:
    """An uploaded document, for the admins who review it: rider documents (riders.view
    in the rider's country) and kitchen licences (partners.view in the kitchen's city)."""
    from core_api.modules.catalog.models.restaurant import Restaurant
    from core_api.modules.catalog.service.lookup import restaurant_city_code

    parts = key.split("/")
    if len(parts) != 3 or parts[0] not in ("rider_document", "partner_document"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        owner = uuid.UUID(parts[1])
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    if parts[0] == "rider_document":
        u = await db.get(User, owner)
        if u is None or not authz.can_within(admin.assignments, "riders.view", u.country):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    else:
        kitchens = (await db.execute(select(Restaurant).where(Restaurant.owner_id == owner, Restaurant.fssai_document_key == key))).scalars().all()
        scopes = [await restaurant_city_code(db, r.id) for r in kitchens]
        if not any(sc and admin.can("partners.view", sc) for sc in scopes):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    got = await get_storage().get(key)
    if got is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    data, ctype = got
    return Response(content=data, media_type=ctype, headers={"Cache-Control": "private, no-store"})


# ── for realtime (signed) ────────────────────────────────────────────────────

async def signed(request: Request) -> None:
    try:
        internal_auth.verify(request.method, request.url.path, await request.body(),
                             request.headers.get("x-internal-timestamp"), request.headers.get("x-internal-signature"))
    except internal_auth.InternalAuthError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Internal endpoint")


@internal.get("/{rider_id}/ready", dependencies=[Depends(signed)])
async def ready(rider_id: uuid.UUID, db: DB) -> dict:
    o = await onboarding(db, rider_id)
    return {"rider_id": str(rider_id), "ready": o.ready, "country": o.country}
