"""Terms and Privacy per country (R8 F10).

Public: the current published document of a kind for a country (in the asked
language, else English), its version history and any one version. A country with
nothing published gets status "unavailable" and a notice instead of a 404, so the
website can say the document is being prepared and offer the countries that have one.

Signed in: what was updated since the person last accepted (the website's
"We updated our Terms" notice) and accepting it.

Admin (Content → Legal): every admin reads; country managers (for their country)
and super admins write drafts and publish. Every change is in the audit log.
"""
import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.api.dependencies import AdminContext, get_current_active_user, require_permission
from core_api.modules.identity.models.user import User
from core_api.modules.legal import service
from core_api.modules.legal.models import LegalDocument
from shared.db import get_db

router = APIRouter(tags=["Legal"])
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
Me = Annotated[User, Depends(get_current_active_user)]
Reader = Annotated[AdminContext, Depends(require_permission("legal.view"))]
Editor = Annotated[AdminContext, Depends(require_permission("legal.edit"))]

Kind = Literal["terms", "privacy", "kitchen_partner_terms", "delivery_partner_terms"]
CountryQ = Annotated[str, Query(pattern=r"^[A-Za-z]{2}$", description="ISO 3166-1 alpha-2")]
LanguageQ = Annotated[str, Query(pattern=r"^[A-Za-z]{2}(-[A-Za-z]{2})?$")]


def _bad(e: service.LegalError, code: int = status.HTTP_409_CONFLICT) -> HTTPException:
    return HTTPException(code, detail={"code": e.code, "message": e.message})


# ── public ───────────────────────────────────────────────────────────────────

class LegalPage(BaseModel):
    kind: str
    country: str
    status: Literal["published", "superseded", "draft", "unavailable"]
    language: str  # the document's language (English when the asked one has no version)
    requested_language: str
    version: int | None = None
    current_version: int | None = None  # the newest published version (on an older one: where to go back to)
    title: str = ""
    key_points: list[str] = []
    body: str = ""  # Markdown
    effective_date: date | None = None
    published_at: datetime | None = None
    superseded_at: datetime | None = None  # an older version: when the next one replaced it
    summary_of_changes: str | None = None
    available_countries: list[str] = []  # countries with a published document of this kind
    notice: str | None = None  # status "unavailable": why there is nothing to show


class LegalVersion(BaseModel):
    version: int
    status: str
    title: str
    effective_date: date | None
    published_at: datetime | None
    superseded_at: datetime | None
    summary_of_changes: str | None


class LegalHistory(BaseModel):
    kind: str
    country: str
    language: str
    versions: list[LegalVersion]
    available_countries: list[str]


def _page(doc: LegalDocument, requested: str, countries: list[str], current: int | None) -> LegalPage:
    return LegalPage(kind=doc.kind, country=doc.country, status=doc.status, language=doc.language,  # type: ignore[arg-type]
                     requested_language=requested, version=doc.version, current_version=current, title=doc.title,
                     key_points=list(doc.key_points or []), body=doc.body, effective_date=doc.effective_date,
                     published_at=doc.published_at, superseded_at=doc.superseded_at,
                     summary_of_changes=doc.summary_of_changes, available_countries=countries)


@router.get("/legal/{kind}", response_model=LegalPage)
async def current_document(kind: Kind, db: DB, country: CountryQ, language: LanguageQ = "en") -> LegalPage:
    """The published version for the country (language falls back to English)."""
    cc, lang = service.norm_country(country), service.norm_language(language)
    countries = await service.available(db, kind)
    doc = await service.current(db, kind, cc, lang)
    if doc is None:
        return LegalPage(kind=kind, country=cc, status="unavailable", language=service.DEFAULT_LANGUAGE,
                         requested_language=lang, available_countries=countries,
                         notice="This document is being prepared for this country and is pending legal review.")
    return _page(doc, lang, countries, doc.version)


@router.get("/legal/{kind}/versions", response_model=LegalHistory)
async def document_versions(kind: Kind, db: DB, country: CountryQ, language: LanguageQ = "en") -> LegalHistory:
    """Every published version, newest first (empty for a country with none)."""
    cc = service.norm_country(country)
    rows = await service.versions(db, kind, cc, language)
    return LegalHistory(kind=kind, country=cc, language=rows[0].language if rows else service.DEFAULT_LANGUAGE,
                        available_countries=await service.available(db, kind),
                        versions=[LegalVersion(version=d.version or 0, status=d.status, title=d.title,
                                               effective_date=d.effective_date, published_at=d.published_at,
                                               superseded_at=d.superseded_at, summary_of_changes=d.summary_of_changes)
                                  for d in rows])


@router.get("/legal/{kind}/versions/{number}", response_model=LegalPage)
async def document_version(kind: Kind, number: int, db: DB, country: CountryQ, language: LanguageQ = "en") -> LegalPage:
    """One published version (current or superseded)."""
    cc, lang = service.norm_country(country), service.norm_language(language)
    doc = await service.version(db, kind, cc, number, lang)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND", "message": "No such version"})
    newest = await service.current(db, kind, cc, lang)
    return _page(doc, lang, await service.available(db, kind), newest.version if newest else None)


# ── signed in ────────────────────────────────────────────────────────────────

class LegalPending(BaseModel):
    kind: str
    country: str
    version: int
    title: str
    effective_date: date | None
    summary_of_changes: str | None


class LegalAcceptIn(BaseModel):
    kinds: list[Kind] = Field(min_length=1, max_length=4)


class LegalAccepted(BaseModel):
    kind: str
    version: int


@router.get("/me/legal/pending", response_model=list[LegalPending])
async def my_pending(me: Me, db: DB) -> list[LegalPending]:
    """Documents published since you last accepted them (show "We updated our Terms" once)."""
    docs = await service.pending(db, me.id, me.role, me.country, me.preferred_locale)
    return [LegalPending(kind=d.kind, country=d.country, version=d.version or 0, title=d.title,
                            effective_date=d.effective_date, summary_of_changes=d.summary_of_changes) for d in docs]


@router.post("/me/legal/accept", response_model=list[LegalAccepted])
async def accept(data: LegalAcceptIn, request: Request, me: Me, db: DB) -> list[LegalAccepted]:
    """Accept the current versions of these kinds (dismissing or continuing past the notice)."""
    rows = await service.record_acceptance(db, me.id, me.country, data.kinds, language=me.preferred_locale,
                                           client=service.client_info(request))
    return [LegalAccepted(kind=r.kind, version=r.version) for r in rows]


# ── admin: Content → Legal ───────────────────────────────────────────────────

class LegalAdminDocument(BaseModel):
    id: uuid.UUID
    kind: str
    country: str
    language: str
    version: int | None
    status: str
    title: str
    key_points: list[str]
    effective_date: date | None
    summary_of_changes: str | None
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None
    superseded_at: datetime | None
    can_edit: bool  # you may edit and publish this country's documents


class LegalAdminDocumentFull(LegalAdminDocument):
    body: str
    created_by_name: str | None
    published_by_name: str | None


class LegalAuditEntry(BaseModel):
    at: datetime
    action: str
    actor: str | None
    before: dict | None
    after: dict | None


class LegalAdminDetail(BaseModel):
    document: LegalAdminDocumentFull
    history: list[LegalAuditEntry]  # this document's changes, oldest first


class LegalDraftIn(BaseModel):
    kind: Kind
    country: str = Field(pattern=r"^[A-Za-z]{2}$")
    language: str = Field(default="en", pattern=r"^[a-z]{2}$")
    title: str | None = Field(default=None, max_length=200)
    key_points: list[Annotated[str, Field(max_length=300)]] | None = Field(default=None, max_length=12)
    body: str | None = Field(default=None, max_length=200_000)
    effective_date: date | None = None
    summary_of_changes: str | None = Field(default=None, max_length=500)


class LegalDraftPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    key_points: list[Annotated[str, Field(max_length=300)]] | None = Field(default=None, max_length=12)
    body: str | None = Field(default=None, max_length=200_000)
    effective_date: date | None = None
    summary_of_changes: str | None = Field(default=None, max_length=500)


def _admin_doc(d: LegalDocument, admin: AdminContext) -> LegalAdminDocument:
    return LegalAdminDocument(id=d.id, kind=d.kind, country=d.country, language=d.language, version=d.version, status=d.status,
                         title=d.title, key_points=list(d.key_points or []), effective_date=d.effective_date,
                         summary_of_changes=d.summary_of_changes, created_at=d.created_at, updated_at=d.updated_at,
                         published_at=d.published_at, superseded_at=d.superseded_at,
                         can_edit=admin.can("legal.edit", d.country))


async def _doc_for(db: AsyncSession, doc_id: uuid.UUID, admin: AdminContext, edit: bool = False) -> LegalDocument:
    from shared import authz

    d = await db.get(LegalDocument, doc_id)
    if d is None or not authz.can_within(admin.assignments, "legal.view", d.country):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND", "message": "Document not found"})
    if edit:
        admin.require("legal.edit", d.country)
    return d


async def _names(db: AsyncSession, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {u.id: u.full_name for u in (await db.execute(select(User).where(User.id.in_(ids)))).scalars()}


@router.get("/admin/legal/documents", response_model=list[LegalAdminDocument])
async def admin_documents(admin: Reader, db: DB, country: str | None = Query(None, pattern=r"^[A-Za-z]{2}$"),
                          kind: Kind | None = None, language: str | None = Query(None, pattern=r"^[a-z]{2}$")) -> list[LegalAdminDocument]:
    """Every document you can see (drafts, published, superseded), newest first per document."""
    from shared import authz

    q = select(LegalDocument).order_by(LegalDocument.country, LegalDocument.kind, LegalDocument.language,
                                       LegalDocument.version.desc().nulls_first())
    if country:
        q = q.where(LegalDocument.country == country.upper())
    if kind:
        q = q.where(LegalDocument.kind == kind)
    if language:
        q = q.where(LegalDocument.language == language)
    rows = [d for d in (await db.execute(q)).scalars() if authz.can_within(admin.assignments, "legal.view", d.country)]
    return [_admin_doc(d, admin) for d in rows]


async def _detail(db: AsyncSession, d: LegalDocument, admin: AdminContext) -> LegalAdminDetail:
    from core_api.modules.audit.service import history

    log = await history(db, "legal_document", [str(d.id)])
    names = await _names(db, {d.created_by, d.published_by, *(e.actor_id for e in log)})
    full = LegalAdminDocumentFull(**_admin_doc(d, admin).model_dump(), body=d.body, created_by_name=names.get(d.created_by),  # type: ignore[arg-type]
                             published_by_name=names.get(d.published_by))  # type: ignore[arg-type]
    return LegalAdminDetail(document=full, history=[
        LegalAuditEntry(at=e.at, action=e.action, actor=names.get(e.actor_id), before=e.before, after=e.after) for e in log])  # type: ignore[arg-type]


@router.get("/admin/legal/documents/{doc_id}", response_model=LegalAdminDetail)
async def admin_document(doc_id: uuid.UUID, admin: Reader, db: DB) -> LegalAdminDetail:
    """One document in full, with its audit history."""
    return await _detail(db, await _doc_for(db, doc_id, admin), admin)


@router.post("/admin/legal/documents", response_model=LegalAdminDetail, status_code=status.HTTP_201_CREATED)
async def admin_new_draft(data: LegalDraftIn, admin: Editor, db: DB) -> LegalAdminDetail:
    """Start a draft (a copy of the published version unless a body is sent)."""
    from core_api.modules.audit.service import record

    admin.require("legal.edit", data.country.upper())
    try:
        d = await service.create_draft(db, admin.user.id, kind=data.kind, country=data.country, language=data.language,
                                       title=data.title, key_points=data.key_points, body=data.body,
                                       effective_date=data.effective_date, summary_of_changes=data.summary_of_changes)
    except service.LegalError as e:
        raise _bad(e)
    await record(db, actor_id=admin.user.id, action="legal.draft_created", entity_type="legal_document", entity_id=d.id,
                 scope=d.country, after=service.snapshot(d))
    await db.refresh(d)
    return await _detail(db, d, admin)


@router.patch("/admin/legal/documents/{doc_id}", response_model=LegalAdminDetail)
async def admin_edit_draft(doc_id: uuid.UUID, data: LegalDraftPatch, admin: Editor, db: DB) -> LegalAdminDetail:
    """Edit a draft: title, key points, Markdown body, effective date, what changed."""
    from core_api.modules.audit.service import record

    d = await _doc_for(db, doc_id, admin, edit=True)
    before = service.snapshot(d)
    try:
        await service.update_draft(db, d, data.model_dump(exclude_unset=True))
    except service.LegalError as e:
        raise _bad(e)
    await record(db, actor_id=admin.user.id, action="legal.draft_edited", entity_type="legal_document", entity_id=d.id,
                 scope=d.country, before=before, after=service.snapshot(d))
    await db.refresh(d)
    return await _detail(db, d, admin)


@router.post("/admin/legal/documents/{doc_id}/publish", response_model=LegalAdminDetail)
async def admin_publish(doc_id: uuid.UUID, admin: Editor, db: DB) -> LegalAdminDetail:
    """Publish the draft as the next version; the previous version is superseded
    and stays in the history. Signed-in people see "We updated our Terms" once."""
    from core_api.modules.audit.service import record

    d = await _doc_for(db, doc_id, admin, edit=True)
    before = service.snapshot(d)
    try:
        d, previous = await service.publish(db, d, admin.user.id)
    except service.LegalError as e:
        raise _bad(e)
    await record(db, actor_id=admin.user.id, action="legal.published", entity_type="legal_document", entity_id=d.id,
                 scope=d.country, before=before, after={**service.snapshot(d), "supersedes": previous.version if previous else None})
    if previous is not None:
        await record(db, actor_id=admin.user.id, action="legal.superseded", entity_type="legal_document",
                     entity_id=previous.id, scope=previous.country, before={"status": "published", "version": previous.version},
                     after={"status": "superseded", "superseded_by": d.version})
    await db.refresh(d)
    return await _detail(db, d, admin)


@router.delete("/admin/legal/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_discard_draft(doc_id: uuid.UUID, admin: Editor, db: DB) -> None:
    """Throw a draft away (published versions are kept forever)."""
    from core_api.modules.audit.service import record

    d = await _doc_for(db, doc_id, admin, edit=True)
    before = service.snapshot(d)
    try:
        await service.discard(db, d)
    except service.LegalError as e:
        raise _bad(e)
    await record(db, actor_id=admin.user.id, action="legal.draft_discarded", entity_type="legal_document",
                 entity_id=doc_id, scope=before["country"], before=before)
