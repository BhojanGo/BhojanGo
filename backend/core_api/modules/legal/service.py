"""Legal documents: the published version per kind, country and language, the
version history, drafts and publishing, and acceptance records (R8 F10).

The contract other modules call when they create an account:

    from core_api.modules.legal.service import record_acceptance, client_info
    await record_acceptance(db, user.id, country.code, kinds=("terms", "privacy"),
                            client=client_info(request))

It records the current published version of each kind for the country (English
when the person's language has no version of its own); a kind the country has
no published document for is skipped (nothing to accept yet), and accepting the
same version twice is a no-op.
"""
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.legal.models import KINDS, LegalAcceptance, LegalDocument

DEFAULT_LANGUAGE = "en"
SOURCES = ("web", "app")
SIGN_UP_KINDS = ("terms", "privacy")
# What each kind of account agrees to (the partner terms only once a country publishes them).
ROLE_KINDS: dict[str, tuple[str, ...]] = {
    "customer": SIGN_UP_KINDS,
    "restaurant_owner": (*SIGN_UP_KINDS, "kitchen_partner_terms"),
    "driver": (*SIGN_UP_KINDS, "delivery_partner_terms"),
}


class LegalError(ValueError):
    """A change the rules don't allow (code for the API's error body)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ClientInfo:
    """Where an acceptance came from: kept minimal (no device id, no location)."""

    source: str = "app"
    ip: str | None = None
    user_agent: str | None = None


def source_for(user_agent: str | None, hint: str | None = None) -> str:
    """web or app: an explicit X-Client header if it says so, else browsers send
    "Mozilla/..." and the apps' HTTP clients (okhttp, CFNetwork, Expo) don't."""
    if hint and hint.strip().lower() in SOURCES:
        return hint.strip().lower()
    return "web" if user_agent and user_agent.startswith("Mozilla/") else "app"


def client_info(request: Any) -> ClientInfo:
    """From a FastAPI/Starlette request (None → an app with nothing known)."""
    if request is None:
        return ClientInfo()
    from shared.client_ip import client_ip

    ua = request.headers.get("user-agent")
    try:
        ip = client_ip(request)
    except Exception:  # noqa: BLE001 - evidence is best effort, never a reason to fail a sign-up
        ip = None
    return ClientInfo(source=source_for(ua, request.headers.get("x-client")), ip=(ip or None) and ip[:45],
                      user_agent=ua[:160] if ua else None)


def norm_country(code: str | None) -> str:
    return (code or "").strip().upper()[:2]


def norm_language(code: str | None) -> str:
    """"te-IN" → "te"; empty → English."""
    return ((code or DEFAULT_LANGUAGE).strip().lower().split("-")[0] or DEFAULT_LANGUAGE)[:8]


def check_kind(kind: str) -> str:
    if kind not in KINDS:
        raise LegalError("KIND", f"Unknown document kind {kind!r}; one of {', '.join(KINDS)}")
    return kind


# ── reading ──────────────────────────────────────────────────────────────────

async def _published(db: AsyncSession, kind: str, country: str, language: str) -> LegalDocument | None:
    return (await db.execute(select(LegalDocument).where(
        LegalDocument.kind == kind, LegalDocument.country == country, LegalDocument.language == language,
        LegalDocument.status == "published").order_by(LegalDocument.version.desc()).limit(1))).scalar_one_or_none()


async def current(db: AsyncSession, kind: str, country: str, language: str | None = None) -> LegalDocument | None:
    """The published version in the language, else in English; None when the
    country has none (the page then says the document is being prepared)."""
    country, language = norm_country(country), norm_language(language)
    doc = await _published(db, kind, country, language)
    if doc is None and language != DEFAULT_LANGUAGE:
        doc = await _published(db, kind, country, DEFAULT_LANGUAGE)
    return doc


async def _history_language(db: AsyncSession, kind: str, country: str, language: str) -> str:
    """The language whose history to show: the requested one if it has any
    published version, else English (the same fallback as current)."""
    if language == DEFAULT_LANGUAGE:
        return language
    n = (await db.execute(select(func.count(LegalDocument.id)).where(
        LegalDocument.kind == kind, LegalDocument.country == country, LegalDocument.language == language,
        LegalDocument.version.is_not(None)))).scalar() or 0
    return language if n else DEFAULT_LANGUAGE


async def versions(db: AsyncSession, kind: str, country: str, language: str | None = None) -> list[LegalDocument]:
    """Every published version (current and superseded), newest first."""
    country, language = norm_country(country), norm_language(language)
    language = await _history_language(db, kind, country, language)
    return list((await db.execute(select(LegalDocument).where(
        LegalDocument.kind == kind, LegalDocument.country == country, LegalDocument.language == language,
        LegalDocument.version.is_not(None)).order_by(LegalDocument.version.desc()))).scalars())


async def version(db: AsyncSession, kind: str, country: str, number: int, language: str | None = None) -> LegalDocument | None:
    country, language = norm_country(country), norm_language(language)
    language = await _history_language(db, kind, country, language)
    return (await db.execute(select(LegalDocument).where(
        LegalDocument.kind == kind, LegalDocument.country == country, LegalDocument.language == language,
        LegalDocument.version == number))).scalar_one_or_none()


async def available(db: AsyncSession, kind: str) -> list[str]:
    """Countries with a published document of this kind (the page's country switcher)."""
    rows = await db.execute(select(LegalDocument.country).where(
        LegalDocument.kind == kind, LegalDocument.status == "published").distinct().order_by(LegalDocument.country))
    return [c for (c,) in rows.all()]


# ── acceptance ───────────────────────────────────────────────────────────────

async def record_acceptance(
    db: AsyncSession,
    user_id: uuid.UUID,
    country_code: str,
    kinds: Iterable[str] = SIGN_UP_KINDS,
    source: str | None = None,
    *,
    language: str | None = None,
    client: ClientInfo | None = None,
) -> list[LegalAcceptance]:
    """Record that the person accepted the current published version of each
    kind for their country. Returns the new rows (already-accepted versions and
    kinds with nothing published are skipped)."""
    client = client or ClientInfo()
    src = source if source in SOURCES else client.source if client.source in SOURCES else "app"
    country = norm_country(country_code)
    out: list[LegalAcceptance] = []
    for kind in dict.fromkeys(kinds):
        doc = await current(db, check_kind(kind), country, language)
        if doc is None or doc.version is None:
            continue
        seen = (await db.execute(select(LegalAcceptance.id).where(
            LegalAcceptance.user_id == user_id, LegalAcceptance.document_id == doc.id))).first()
        if seen:
            continue
        row = LegalAcceptance(user_id=user_id, document_id=doc.id, kind=kind, country=country, version=doc.version,
                              source=src, ip=client.ip, user_agent=client.user_agent)
        db.add(row)
        out.append(row)
    if out:
        await db.flush()
    return out


async def accepted_versions(db: AsyncSession, user_id: uuid.UUID, country: str) -> dict[str, int]:
    """The newest version of each kind the person accepted in this country."""
    rows = await db.execute(select(LegalAcceptance.kind, func.max(LegalAcceptance.version)).where(
        LegalAcceptance.user_id == user_id, LegalAcceptance.country == norm_country(country)).group_by(LegalAcceptance.kind))
    return {k: v for k, v in rows.all()}


async def pending(db: AsyncSession, user_id: uuid.UUID, role: str, country: str,
                  language: str | None = None) -> list[LegalDocument]:
    """Published documents for the person's kind of account that are newer than
    what they accepted (the website's "We updated our Terms" notice)."""
    done = await accepted_versions(db, user_id, country)
    out = []
    for kind in ROLE_KINDS.get(role, SIGN_UP_KINDS):
        doc = await current(db, kind, country, language)
        if doc is not None and doc.version is not None and doc.version > done.get(kind, 0):
            out.append(doc)
    return out


# ── admin: drafts and publishing ─────────────────────────────────────────────

def snapshot(doc: LegalDocument) -> dict[str, Any]:
    """What the audit log keeps of a document (the body by length and start, so
    the log stays small; every published version is itself kept in full)."""
    return {"kind": doc.kind, "country": doc.country, "language": doc.language, "version": doc.version,
            "status": doc.status, "title": doc.title, "key_points": list(doc.key_points or []),
            "effective_date": doc.effective_date.isoformat() if doc.effective_date else None,
            "summary_of_changes": doc.summary_of_changes, "body_chars": len(doc.body or ""),
            "body_start": (doc.body or "")[:200]}


def clean_points(points: Sequence[str] | None) -> list[str]:
    return [p.strip() for p in (points or []) if p and p.strip()][:12]


async def open_draft(db: AsyncSession, kind: str, country: str, language: str) -> LegalDocument | None:
    return (await db.execute(select(LegalDocument).where(
        LegalDocument.kind == kind, LegalDocument.country == country, LegalDocument.language == language,
        LegalDocument.status == "draft").order_by(LegalDocument.created_at.desc()).limit(1))).scalar_one_or_none()


async def create_draft(db: AsyncSession, actor_id: uuid.UUID | None, *, kind: str, country: str, language: str = "en",
                       title: str | None = None, key_points: Sequence[str] | None = None, body: str | None = None,
                       effective_date: date | None = None, summary_of_changes: str | None = None) -> LegalDocument:
    """A new draft, by default a copy of the current published version (so an
    edit starts from what's live). One open draft per kind, country and language."""
    kind, country, language = check_kind(kind), norm_country(country), norm_language(language)
    if len(country) != 2 or not country.isalpha():
        raise LegalError("COUNTRY", "Use a two-letter country code")
    if await open_draft(db, kind, country, language) is not None:
        raise LegalError("DRAFT_EXISTS", "There is already a draft for this document: edit or discard it first")
    # A first translation starts from the English text, to be translated in place.
    base = await _published(db, kind, country, language) or await _published(db, kind, country, DEFAULT_LANGUAGE)
    doc = LegalDocument(
        kind=kind, country=country, language=language, version=None, status="draft",
        title=(title or (base.title if base else "")).strip() or kind.replace("_", " ").capitalize(),
        key_points=clean_points(key_points) if key_points is not None else list(base.key_points if base else []),
        body=body if body is not None else (base.body if base else ""),
        effective_date=effective_date, summary_of_changes=summary_of_changes, created_by=actor_id)
    db.add(doc)
    await db.flush()
    return doc


async def update_draft(db: AsyncSession, doc: LegalDocument, changes: dict[str, Any]) -> LegalDocument:
    if doc.status != "draft":
        raise LegalError("NOT_DRAFT", "Only a draft can be edited; start a new draft to change a published version")
    for field in ("title", "body", "effective_date", "summary_of_changes"):
        if field in changes:
            value = changes[field]
            if value is None and field in ("title", "body"):
                continue
            setattr(doc, field, value.strip() if field == "title" and isinstance(value, str) else value)
    if "key_points" in changes:
        doc.key_points = clean_points(changes["key_points"])
    if not doc.title:
        raise LegalError("TITLE", "Give the document a title")
    await db.flush()
    return doc


async def publish(db: AsyncSession, doc: LegalDocument, actor_id: uuid.UUID | None,
                  today: date | None = None) -> tuple[LegalDocument, LegalDocument | None]:
    """The draft becomes the next version; the version before it is superseded
    (kept, readable in the history). Returns (published, superseded or None)."""
    if doc.status != "draft":
        raise LegalError("NOT_DRAFT", "This version is already published")
    if not doc.title.strip() or len(doc.body.strip()) < 20:
        raise LegalError("EMPTY", "Write the document before publishing it")
    # Serialise publishing for this document (two admins clicking at once can't both get version N).
    await db.execute(select(LegalDocument.id).where(
        LegalDocument.kind == doc.kind, LegalDocument.country == doc.country, LegalDocument.language == doc.language)
        .with_for_update())
    last = (await db.execute(select(func.max(LegalDocument.version)).where(
        LegalDocument.kind == doc.kind, LegalDocument.country == doc.country,
        LegalDocument.language == doc.language))).scalar() or 0
    previous = await _published(db, doc.kind, doc.country, doc.language)
    now = datetime.now(UTC)
    if previous is not None:
        previous.status, previous.superseded_at = "superseded", now
        await db.flush()
    doc.status, doc.version, doc.published_at, doc.published_by = "published", last + 1, now, actor_id
    doc.effective_date = doc.effective_date or today or now.date()
    await db.flush()
    return doc, previous


async def discard(db: AsyncSession, doc: LegalDocument) -> None:
    if doc.status != "draft":
        raise LegalError("NOT_DRAFT", "Published versions are kept; only a draft can be discarded")
    await db.delete(doc)
    await db.flush()
