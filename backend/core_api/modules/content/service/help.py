"""Help centre reads and writes (round 8, F9).

Which article a visitor gets: for each slug, the first published one of
    (their country, their language), (their country, English),
    (every country, their language), (every country, English).
A country's own version wins over the global one, because it is the one with
that country's facts (FSSAI and GST in India, Stripe in the US).

Search is Postgres full-text across title, summary and body of every article
the visitor could get (all four kinds above), so a visitor reading in Hindi
who types English words still finds the article; each hit is answered with
the visitor's best version of that slug. Words match as prefixes, so results
come as they type ("refu" finds refunds).
"""
import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, literal_column, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.content.models import GLOBAL, LANGUAGES, TOPICS, HelpArticle, HelpArticleVersion, HelpVote

CONTENT_FIELDS = ("title", "summary", "body", "topic", "popular", "related")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Full-text configurations Postgres ships with, per language; the rest use "simple".
FTS_CONFIG = {"en": "english", "es": "spanish"}


def norm_country(country: str | None) -> str | None:
    c = (country or "").strip().upper()
    return c if re.fullmatch(r"[A-Z]{2}", c) else None


def norm_language(language: str | None) -> str:
    lang = (language or "").strip().lower()[:2]
    return lang if lang in LANGUAGES else "en"


def preference(country: str | None, language: str) -> list[tuple[str, str]]:
    """(country, language) pairs in the order a visitor gets them."""
    order: list[tuple[str, str]] = []
    for c in ([country] if country else []) + [GLOBAL]:
        for lang in dict.fromkeys([language, "en"]):
            order.append((c, lang))
    return order


def pick_best(rows: list[HelpArticle], country: str | None, language: str) -> dict[str, HelpArticle]:
    """slug -> the visitor's best version among rows."""
    rank = {pair: i for i, pair in enumerate(preference(country, language))}
    best: dict[str, HelpArticle] = {}
    for r in rows:
        k = rank.get((r.country, r.language))
        if k is None:
            continue
        cur = best.get(r.slug)
        if cur is None or k < rank[(cur.country, cur.language)]:
            best[r.slug] = r
    return best


def _visible(country: str | None, language: str):  # type: ignore[no-untyped-def]
    countries = [GLOBAL] + ([country] if country else [])
    return (HelpArticle.status == "published", HelpArticle.country.in_(countries),
            HelpArticle.language.in_(list(dict.fromkeys([language, "en"]))))


async def visible(db: AsyncSession, country: str | None, language: str) -> dict[str, HelpArticle]:
    rows = list((await db.execute(select(HelpArticle).where(*_visible(country, language)))).scalars())
    return pick_best(rows, country, language)


def ordered(articles: list[HelpArticle]) -> list[HelpArticle]:
    return sorted(articles, key=lambda a: (a.popular == 0, a.popular, a.title.lower()))


def topic_counts(best: dict[str, HelpArticle]) -> list[dict[str, Any]]:
    return [{"topic": t, "count": sum(1 for a in best.values() if a.topic == t)} for t in TOPICS]


def popular(best: dict[str, HelpArticle], limit: int = 8) -> list[HelpArticle]:
    return [a for a in ordered(list(best.values())) if a.popular > 0][:limit]


WORD = re.compile(r"[\wऀ-෿]+", re.UNICODE)


def prefix_query(q: str) -> str | None:
    """'refund late' -> "refund:* & late:*" (letters and digits only, so it can't break to_tsquery)."""
    words = [w.lower() for w in WORD.findall(q)][:8]
    return " & ".join(f"{w}:*" for w in words) if words else None


def _weight(w: str):  # type: ignore[no-untyped-def]
    """A setweight() label: Postgres wants the one-byte "char" type, not varchar."""
    assert w in "ABCD"
    return literal_column(f"'{w}'::\"char\"")


def _cfg(name: str):  # type: ignore[no-untyped-def]
    """A full-text configuration by name (only names from FTS_CONFIG or "simple")."""
    assert name in ("simple", *FTS_CONFIG.values())
    return literal_column(f"'{name}'::regconfig")


async def search(db: AsyncSession, q: str, country: str | None, language: str, limit: int = 10) -> list[HelpArticle]:
    pq = prefix_query(q)
    if not pq:
        return []
    cfg = FTS_CONFIG.get(language, "simple")
    simple = _cfg("simple")
    doc = (func.setweight(func.to_tsvector(simple, HelpArticle.title), _weight("A"))
           .op("||")(func.setweight(func.to_tsvector(simple, HelpArticle.summary), _weight("B")))
           .op("||")(func.setweight(func.to_tsvector(simple, HelpArticle.body), _weight("C"))))
    stemmed = func.to_tsvector(_cfg(cfg), func.concat_ws(" ", HelpArticle.title, HelpArticle.summary, HelpArticle.body))
    prefix = func.to_tsquery(simple, pq)
    words = func.websearch_to_tsquery(_cfg(cfg), q[:200])
    rank = func.ts_rank(doc, prefix) + func.ts_rank(stemmed, words)
    rows = (await db.execute(
        select(HelpArticle, rank.label("rank")).where(*_visible(country, language), or_(doc.op("@@")(prefix), stemmed.op("@@")(words)))
        .order_by(rank.desc()).limit(100))).all()
    if not rows:
        return []
    best = await visible(db, country, language)
    out: list[HelpArticle] = []
    seen: set[str] = set()
    for row, _ in rows:
        if row.slug in seen or row.slug not in best:
            continue
        seen.add(row.slug)
        out.append(best[row.slug])
    return out[:limit]


# ── votes ────────────────────────────────────────────────────────────────────

def voter_key(voter: str, ip: str) -> str:
    """The browser's random id (or, without one, the address), hashed: we never keep either."""
    return hashlib.sha256(f"help-vote:{voter or ip}".encode()).hexdigest()


async def vote(db: AsyncSession, article: HelpArticle, voter: str, helpful: bool) -> None:
    from sqlalchemy.dialects.postgresql import insert

    stmt = insert(HelpVote).values(id=uuid.uuid4(), article_id=article.id, voter=voter, helpful=helpful)
    await db.execute(stmt.on_conflict_do_update(constraint="uq_help_votes_article_voter",
                                                set_={"helpful": helpful, "at": func.now()}))


async def vote_counts(db: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int]]:
    if not ids:
        return {}
    rows = (await db.execute(select(HelpVote.article_id, HelpVote.helpful, func.count()).where(HelpVote.article_id.in_(ids))
                             .group_by(HelpVote.article_id, HelpVote.helpful))).all()
    out: dict[uuid.UUID, list[int]] = {}
    for aid, helpful, n in rows:
        out.setdefault(aid, [0, 0])[0 if helpful else 1] += n
    return {k: (v[0], v[1]) for k, v in out.items()}


# ── writing (the admin console) ──────────────────────────────────────────────

def content_of(a: HelpArticle) -> dict[str, Any]:
    return {"title": a.title, "summary": a.summary, "body": a.body, "topic": a.topic, "popular": a.popular,
            "related": list(a.related or [])}


def working_copy(a: HelpArticle) -> dict[str, Any]:
    """What the editor shows: unpublished changes if any, else the article."""
    return {**content_of(a), **(a.draft or {})}


async def add_version(db: AsyncSession, a: HelpArticle, action: str, by: uuid.UUID | None) -> None:
    db.add(HelpArticleVersion(article_id=a.id, version=a.version, action=action, content=working_copy(a),
                              status=a.status, by=by))


def apply(a: HelpArticle, content: dict[str, Any]) -> None:
    for k in CONTENT_FIELDS:
        if k in content:
            setattr(a, k, content[k])


def save(a: HelpArticle, changes: dict[str, Any], by: uuid.UUID | None) -> None:
    """Save from the editor. A draft article changes in place; a published one
    keeps its live text and holds the changes until they are published."""
    if a.status == "published":
        merged = {**working_copy(a), **changes}
        a.draft = None if merged == content_of(a) else merged
    else:
        apply(a, changes)
    a.version += 1
    a.updated_at, a.updated_by = datetime.now(UTC), by


def publish(a: HelpArticle, by: uuid.UUID | None) -> None:
    if a.draft:
        apply(a, a.draft)
        a.draft = None
    a.status = "published"
    a.version += 1
    now = datetime.now(UTC)
    a.published_at, a.updated_at, a.updated_by = now, now, by


def unpublish(a: HelpArticle, by: uuid.UUID | None) -> None:
    if a.draft:  # back to a draft: the editor's text becomes the article's
        apply(a, a.draft)
        a.draft = None
    a.status = "draft"
    a.version += 1
    a.updated_at, a.updated_by = datetime.now(UTC), by


# ── seed files (tools/seed/help/<language>/<slug>[.<CC>].md) ────────────────

@dataclass
class SeedArticle:
    slug: str
    topic: str
    country: str
    language: str
    title: str
    summary: str
    body: str
    popular: int
    related: list[str]


def parse_seed(text: str, language: str) -> SeedArticle:
    """Front matter (`key: value` lines between --- lines), then the Markdown body."""
    text = text.replace("\r\n", "\n").lstrip("﻿")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        raise ValueError("missing front matter")
    meta: dict[str, str] = {}
    for line in m.group(1).split("\n"):
        if line.strip():
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    a = SeedArticle(slug=meta["slug"], topic=meta["topic"], country=meta.get("country", GLOBAL) or GLOBAL, language=language,
                    title=meta["title"], summary=meta.get("summary", ""), body=m.group(2).strip() + "\n",
                    popular=int(meta.get("popular") or 0),
                    related=[s.strip() for s in meta.get("related", "").split(",") if s.strip()])
    problems = validate(a.slug, a.topic, a.country, a.language, a.title, a.summary)
    if problems:
        raise ValueError("; ".join(problems))
    return a


def load_seed_dir(root: Path) -> list[SeedArticle]:
    out = []
    for path in sorted(root.glob("*/*.md")):
        a = parse_seed(path.read_text(encoding="utf-8"), path.parent.name)
        stem = path.name[:-3]
        expected = a.slug if a.country == GLOBAL else f"{a.slug}.{a.country}"
        if stem != expected:
            raise ValueError(f"{path}: file name should be {expected}.md")
        out.append(a)
    return out


def validate(slug: str, topic: str, country: str, language: str, title: str, summary: str) -> list[str]:
    problems = []
    if not SLUG.match(slug) or len(slug) > 80:
        problems.append("slug: lowercase letters, digits and hyphens")
    if topic not in TOPICS:
        problems.append(f"topic: one of {', '.join(TOPICS)}")
    if country != GLOBAL and not re.fullmatch(r"[A-Z]{2}", country):
        problems.append("country: a country code or * for every country")
    if language not in LANGUAGES:
        problems.append(f"language: one of {', '.join(LANGUAGES)}")
    if not title.strip() or len(title) > 160:
        problems.append("title: 1 to 160 characters")
    if len(summary) > 300:
        problems.append("summary: up to 300 characters")
    return problems
