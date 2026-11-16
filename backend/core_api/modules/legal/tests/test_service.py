"""Legal documents (R8 F10) on SQLite: the published version with the English
fallback, publishing supersedes and numbers versions, acceptances are recorded
once per version, and the "We updated our Terms" list follows them."""
import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core_api.modules.legal import service
from core_api.modules.legal.models import LegalAcceptance, LegalDocument
from shared.db import Base

BODY = "## 1. Who we are\n\nBhojanGo connects you with independent kitchens."


@pytest_asyncio.fixture
async def db():  # type: ignore[no-untyped-def]
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[LegalDocument.__table__, LegalAcceptance.__table__])
    async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()


async def published(db: AsyncSession, kind: str = "terms", country: str = "IN", language: str = "en",
                    title: str = "Terms of use") -> LegalDocument:
    d = await service.create_draft(db, None, kind=kind, country=country, language=language, title=title,
                                   key_points=["One", "  ", "Two"], body=BODY, effective_date=date(2026, 11, 15))
    d, _ = await service.publish(db, d, None)
    return d


def test_source_from_the_client() -> None:
    assert service.source_for("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0)") == "web"
    assert service.source_for("okhttp/4.12.0") == "app"
    assert service.source_for(None) == "app"
    assert service.source_for("Mozilla/5.0", hint="app") == "app"
    assert service.source_for("okhttp", hint=" WEB ") == "web"
    assert service.source_for("okhttp", hint="tablet") == "app"


def test_normalising() -> None:
    assert service.norm_language("te-IN") == "te"
    assert service.norm_language(None) == "en"
    assert service.norm_country(" in ") == "IN"
    with pytest.raises(service.LegalError):
        service.check_kind("cookies")


def test_client_info_keeps_it_minimal() -> None:
    class Req:
        headers = {"user-agent": "Mozilla/5.0 " + "x" * 400}
        client = type("C", (), {"host": "203.0.113.9"})()

    info = service.client_info(Req())
    assert info.source == "web" and info.ip == "203.0.113.9" and len(info.user_agent or "") == 160
    assert service.client_info(None) == service.ClientInfo()


async def test_current_falls_back_to_english_and_a_country_without_one_is_none(db: AsyncSession) -> None:
    d = await published(db)
    assert d.version == 1 and d.status == "published" and d.key_points == ["One", "Two"]
    assert (await service.current(db, "terms", "in", "te-IN")).id == d.id  # type: ignore[union-attr]
    assert await service.current(db, "terms", "GB", "en") is None
    assert await service.current(db, "privacy", "IN", "en") is None
    assert await service.available(db, "terms") == ["IN"]


async def test_publish_supersedes_and_keeps_history(db: AsyncSession) -> None:
    v1 = await published(db)
    draft = await service.create_draft(db, None, kind="terms", country="IN", language="en")
    assert draft.body == BODY and draft.title == "Terms of use" and draft.version is None  # a copy of what's live
    with pytest.raises(service.LegalError) as e:
        await service.create_draft(db, None, kind="terms", country="IN", language="en")
    assert e.value.code == "DRAFT_EXISTS"
    await service.update_draft(db, draft, {"title": "Terms of use (2027)", "key_points": ["Three"], "title_ignored": 1})
    v2, previous = await service.publish(db, draft, None)
    assert (v2.version, v2.status, previous and previous.id) == (2, "published", v1.id)
    assert v1.status == "superseded" and v1.superseded_at is not None
    assert [d.version for d in await service.versions(db, "terms", "IN")] == [2, 1]
    assert (await service.version(db, "terms", "IN", 1, "hi")).title == "Terms of use"  # type: ignore[union-attr]
    assert (await service.current(db, "terms", "IN")).version == 2  # type: ignore[union-attr]
    with pytest.raises(service.LegalError):
        await service.update_draft(db, v2, {"title": "No"})
    with pytest.raises(service.LegalError):
        await service.publish(db, v2, None)
    with pytest.raises(service.LegalError):
        await service.discard(db, v1)


async def test_an_empty_draft_cant_be_published(db: AsyncSession) -> None:
    d = await service.create_draft(db, None, kind="privacy", country="US", language="en", title="Privacy notice", body="")
    with pytest.raises(service.LegalError) as e:
        await service.publish(db, d, None)
    assert e.value.code == "EMPTY"
    await service.discard(db, d)
    assert await service.open_draft(db, "privacy", "US", "en") is None


async def test_record_acceptance_once_per_version_and_pending(db: AsyncSession) -> None:
    terms = await published(db)
    await published(db, "privacy", title="Privacy notice")
    user = uuid.uuid4()
    rows = await service.record_acceptance(db, user, "IN", client=service.ClientInfo("web", "198.51.100.4", "Mozilla/5.0"))
    assert sorted((r.kind, r.version, r.source) for r in rows) == [("privacy", 1, "web"), ("terms", 1, "web")]
    assert await service.record_acceptance(db, user, "IN") == []  # already accepted
    # Kinds with nothing published (partner terms) are skipped, not an error.
    assert await service.record_acceptance(db, user, "IN", ("delivery_partner_terms",), "app") == []
    assert await service.pending(db, user, "customer", "IN") == []

    draft = await service.create_draft(db, None, kind="terms", country="IN", language="en")
    await service.publish(db, draft, None)
    assert [(d.kind, d.version) for d in await service.pending(db, user, "customer", "IN")] == [("terms", 2)]
    # Someone who never accepted anything (an account from before) sees both.
    assert {d.kind for d in await service.pending(db, uuid.uuid4(), "customer", "IN")} == {"terms", "privacy"}
    rows = await service.record_acceptance(db, user, "IN", ["terms"], "app")
    assert [(r.kind, r.version, r.source) for r in rows] == [("terms", 2, "app")]
    assert await service.pending(db, user, "customer", "IN") == []
    assert await service.accepted_versions(db, user, "IN") == {"terms": 2, "privacy": 1}
    assert terms.status == "superseded"


async def test_a_country_without_documents_records_nothing(db: AsyncSession) -> None:
    await published(db)
    assert await service.record_acceptance(db, uuid.uuid4(), "GB") == []


async def test_a_first_translation_starts_from_the_english_text(db: AsyncSession) -> None:
    await published(db)
    hi = await service.create_draft(db, None, kind="terms", country="IN", language="hi-IN")
    assert (hi.language, hi.body, hi.title, hi.key_points) == ("hi", BODY, "Terms of use", ["One", "Two"])
