"""Help articles in the admin console: Content -> Help (round 8, F9).

Who may do what (shared/authz.py):
- content.view: read every article of a country they can see, and the global
  ones (super admin, country managers, support agents, viewers).
- content.edit: write and publish a country's articles (country managers for
  their country); articles for every country ("*") are the super admin's.
Every create, save, publish and unpublish is a version (the History tab) and an
audit-log row (who and when).
"""
import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.content.models import GLOBAL, HelpArticle, HelpArticleVersion
from core_api.modules.content.service import help as svc
from core_api.modules.identity.api.dependencies import AdminContext, require_permission
from shared import authz
from shared.db import get_db

router = APIRouter(prefix="/ops/help", tags=["Help (admin)"])
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
Viewer = Annotated[AdminContext, Depends(require_permission("content.view"))]
Editor = Annotated[AdminContext, Depends(require_permission("content.edit"))]
Topic = Literal["orders", "payments-refunds", "delivery", "account", "kitchen-partners", "delivery-partners"]
Language = Literal["en", "hi", "te", "ta", "kn", "mr", "bn", "es"]
SLUG = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
COUNTRY = r"^(\*|[A-Z]{2})$"


class Content(BaseModel):
    title: str
    summary: str
    body: str
    topic: str
    popular: int
    related: list[str]


class AdminArticle(BaseModel):
    id: uuid.UUID
    slug: str
    country: str
    language: str
    status: str
    version: int
    live: Content  # what the website shows when published
    draft: Content | None  # unpublished changes to a published article
    helpful_yes: int
    helpful_no: int
    published_at: datetime | None
    updated_at: datetime
    updated_by_name: str | None
    can_edit: bool


class ArticleIn(BaseModel):
    slug: str = Field(min_length=2, max_length=80, pattern=SLUG)
    country: str = Field(pattern=COUNTRY)
    language: Language
    topic: Topic
    title: str = Field(min_length=3, max_length=160)
    summary: str = Field("", max_length=300)
    body: str = Field("", max_length=40000)
    popular: int = Field(0, ge=0, le=99)
    related: list[str] = Field(default_factory=list, max_length=8)


class ArticlePatch(BaseModel):
    topic: Topic | None = None
    title: str | None = Field(None, min_length=3, max_length=160)
    summary: str | None = Field(None, max_length=300)
    body: str | None = Field(None, max_length=40000)
    popular: int | None = Field(None, ge=0, le=99)
    related: list[str] | None = Field(None, max_length=8)


class HistoryEntry(BaseModel):
    version: int
    action: str
    status: str
    at: datetime
    by_name: str | None
    content: Content


def _where(country: str) -> str:
    return GLOBAL if country == GLOBAL else country


async def _names(db: AsyncSession, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    from core_api.modules.identity.models.user import User

    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {u.id: (u.full_name or u.email or "Admin") for u in (await db.execute(select(User).where(User.id.in_(ids)))).scalars()}


async def _out(db: AsyncSession, admin: AdminContext, a: HelpArticle, counts=None, names=None) -> AdminArticle:  # type: ignore[no-untyped-def]
    counts = counts if counts is not None else await svc.vote_counts(db, [a.id])
    names = names if names is not None else await _names(db, {a.updated_by})
    yes, no = counts.get(a.id, (0, 0))
    return AdminArticle(id=a.id, slug=a.slug, country=a.country, language=a.language, status=a.status, version=a.version,
                        live=Content(**svc.content_of(a)), draft=Content(**svc.working_copy(a)) if a.draft else None,
                        helpful_yes=yes, helpful_no=no, published_at=a.published_at, updated_at=a.updated_at,
                        updated_by_name=names.get(a.updated_by) if a.updated_by else None,
                        can_edit=admin.can("content.edit", _where(a.country)))


async def _get(db: AsyncSession, admin: AdminContext, article_id: uuid.UUID, *, edit: bool) -> HelpArticle:
    a = await db.get(HelpArticle, article_id)
    if a is None or not authz.can_within(admin.assignments, "content.view", _where(a.country)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Article not found")
    if edit and not admin.can("content.edit", _where(a.country)):
        who = "every country" if a.country == GLOBAL else a.country
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "FORBIDDEN_SCOPE", "message": f"You can't edit help for {who}"})
    return a


async def _audit(db: AsyncSession, admin: AdminContext, a: HelpArticle, action: str, before: dict | None) -> None:
    from core_api.modules.audit.service import record

    await svc.add_version(db, a, action, admin.user.id)
    await record(db, actor_id=admin.user.id, action=f"help.{action}", entity_type="help_article", entity_id=a.id,
                 scope=_where(a.country), before=before,
                 after={"slug": a.slug, "country": a.country, "language": a.language, "status": a.status,
                        "version": a.version, "title": svc.working_copy(a)["title"]})


@router.get("/articles", response_model=list[AdminArticle])
async def list_articles(admin: Viewer, db: DB, country: str | None = Query(None, pattern=COUNTRY),
                        language: Language | None = None, topic: Topic | None = None,
                        state: Literal["draft", "published", "changes"] | None = Query(None, alias="status"),
                        q: str | None = Query(None, max_length=100)) -> list[AdminArticle]:
    """Every article you may see, filtered. status=changes: published with unpublished changes."""
    stmt = select(HelpArticle).order_by(HelpArticle.topic, HelpArticle.slug, HelpArticle.country, HelpArticle.language)
    if country:
        stmt = stmt.where(HelpArticle.country == country)
    if language:
        stmt = stmt.where(HelpArticle.language == language)
    if topic:
        stmt = stmt.where(HelpArticle.topic == topic)
    if state == "changes":
        stmt = stmt.where(HelpArticle.status == "published", HelpArticle.draft.is_not(None))
    elif state:
        stmt = stmt.where(HelpArticle.status == state)
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(HelpArticle.title.ilike(like), HelpArticle.slug.ilike(like), HelpArticle.summary.ilike(like)))
    rows = [a for a in (await db.execute(stmt.limit(1000))).scalars()
            if authz.can_within(admin.assignments, "content.view", _where(a.country))]
    counts = await svc.vote_counts(db, [a.id for a in rows])
    names = await _names(db, {a.updated_by for a in rows})
    return [await _out(db, admin, a, counts, names) for a in rows]


@router.post("/articles", response_model=AdminArticle, status_code=status.HTTP_201_CREATED)
async def create_article(data: ArticleIn, admin: Editor, db: DB) -> AdminArticle:
    """A new article (a draft), or a new language or country version of a slug."""
    admin.require("content.edit", _where(data.country))
    exists = (await db.execute(select(HelpArticle.id).where(
        HelpArticle.slug == data.slug, HelpArticle.country == data.country, HelpArticle.language == data.language))).first()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={
            "code": "EXISTS", "message": "That article already exists for this country and language; edit it instead"})
    a = HelpArticle(slug=data.slug, country=data.country, language=data.language, topic=data.topic, title=data.title.strip(),
                    summary=data.summary.strip(), body=data.body, popular=data.popular, related=data.related,
                    status="draft", version=1, updated_by=admin.user.id)
    db.add(a)
    await db.flush()
    await _audit(db, admin, a, "created", None)
    await db.flush()
    await db.refresh(a)
    return await _out(db, admin, a)


@router.get("/articles/{article_id}", response_model=AdminArticle)
async def get_article(article_id: uuid.UUID, admin: Viewer, db: DB) -> AdminArticle:
    return await _out(db, admin, await _get(db, admin, article_id, edit=False))


@router.patch("/articles/{article_id}", response_model=AdminArticle)
async def save_article(article_id: uuid.UUID, data: ArticlePatch, admin: Editor, db: DB) -> AdminArticle:
    """Save. A published article keeps showing its live text until you publish."""
    a = await _get(db, admin, article_id, edit=True)
    before = svc.working_copy(a)
    changes = {k: (v.strip() if isinstance(v, str) and k in ("title", "summary") else v)
               for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    svc.save(a, changes, admin.user.id)
    await _audit(db, admin, a, "edited", {"title": before["title"], "status": a.status})
    await db.flush()
    return await _out(db, admin, a)


@router.post("/articles/{article_id}/publish", response_model=AdminArticle)
async def publish_article(article_id: uuid.UUID, admin: Editor, db: DB) -> AdminArticle:
    a = await _get(db, admin, article_id, edit=True)
    before = {"status": a.status, "had_changes": bool(a.draft)}
    svc.publish(a, admin.user.id)
    await _audit(db, admin, a, "published", before)
    await db.flush()
    return await _out(db, admin, a)


@router.post("/articles/{article_id}/unpublish", response_model=AdminArticle)
async def unpublish_article(article_id: uuid.UUID, admin: Editor, db: DB) -> AdminArticle:
    a = await _get(db, admin, article_id, edit=True)
    if a.status != "published":
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "NOT_PUBLISHED", "message": "This article isn't published"})
    svc.unpublish(a, admin.user.id)
    await _audit(db, admin, a, "unpublished", {"status": "published"})
    await db.flush()
    return await _out(db, admin, a)


@router.get("/articles/{article_id}/history", response_model=list[HistoryEntry])
async def article_history(article_id: uuid.UUID, admin: Viewer, db: DB) -> list[HistoryEntry]:
    """Newest first: every version with who made it and when."""
    a = await _get(db, admin, article_id, edit=False)
    rows = list((await db.execute(select(HelpArticleVersion).where(HelpArticleVersion.article_id == a.id)
                                  .order_by(HelpArticleVersion.version.desc(), HelpArticleVersion.at.desc()))).scalars())
    names = await _names(db, {r.by for r in rows})
    return [HistoryEntry(version=r.version, action=r.action, status=r.status, at=r.at,
                         by_name=names.get(r.by) if r.by else "Seed data", content=Content(**r.content)) for r in rows]
