"""The Terms and Privacy drafts (R8 F10) for the base seed: legal/<COUNTRY>-<kind>.md,
each with a small header (title, effective_date, summary, key_points) and a
Markdown body. Seeded as published version 1 in English, for test environments
only: the website shows "Draft: pending legal review" everywhere but production,
and production's documents are written and published in the admin console
(Content → Legal) after legal review.

Idempotent: version 1 is upserted by a fixed id, so running the seed again
refreshes its text; versions an admin published later are left alone.
"""
import json
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import text

HERE = Path(__file__).resolve().parent / "legal"


def parse(path: Path) -> dict:
    """Header between --- lines: `key: value` and `- item` lines under key_points."""
    nl = chr(10)
    raw = nl.join(path.read_text(encoding="utf-8").splitlines()) + nl
    _, header, body = raw.split("---\n", 2)
    meta: dict = {"key_points": []}
    current = None
    for line in header.splitlines():
        if line.startswith("- ") and current == "key_points":
            meta["key_points"].append(line[2:].strip())
        elif ":" in line:
            key, _, value = line.partition(":")
            current = key.strip()
            if value.strip():
                meta[current] = value.strip()
    country, kind = path.stem.split("-", 1)
    return {"country": country, "kind": kind, "title": meta["title"], "summary": meta.get("summary"),
            "effective_date": date.fromisoformat(meta["effective_date"]), "key_points": meta["key_points"],
            "body": body.strip() + "\n"}


def documents() -> list[dict]:
    return [parse(p) for p in sorted(HERE.glob("*.md"))]


async def seed_legal(conn, sid) -> int:  # type: ignore[no-untyped-def]
    n = 0
    for d in documents():
        doc_id: uuid.UUID = sid("legal_document", d["country"], d["kind"], "en", "1")
        other = (await conn.execute(text(
            "SELECT id FROM legal_documents WHERE kind = :k AND country = :c AND language = 'en' AND version = 1"),
            {"k": d["kind"], "c": d["country"]})).scalar()
        if other is not None and other != doc_id:
            continue  # an admin published version 1 themselves
        later = (await conn.execute(text(
            "SELECT count(*) FROM legal_documents WHERE kind = :k AND country = :c AND language = 'en' AND version > 1"),
            {"k": d["kind"], "c": d["country"]})).scalar()
        await conn.execute(text("""
            INSERT INTO legal_documents (id, kind, country, language, version, status, title, key_points, body,
                summary_of_changes, effective_date, published_at, created_at, updated_at)
            VALUES (:id, :kind, :country, 'en', 1, :status, :title, CAST(:points AS jsonb), :body, :summary,
                :effective, now(), now(), now())
            ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, key_points = EXCLUDED.key_points, body = EXCLUDED.body,
                summary_of_changes = EXCLUDED.summary_of_changes, effective_date = EXCLUDED.effective_date, updated_at = now()
            """), {"id": doc_id, "kind": d["kind"], "country": d["country"], "status": "superseded" if later else "published",
                   "title": d["title"], "points": json.dumps(d["key_points"]), "body": d["body"], "summary": d["summary"],
                   "effective": d["effective_date"]})
        # The seed's own accounts accepted version 1 when they "signed up" (so they don't
        # all see "We've updated our policies" until an admin publishes a new version).
        await conn.execute(text("""
            INSERT INTO legal_acceptances (id, user_id, document_id, kind, country, version, source, accepted_at)
            SELECT gen_random_uuid(), u.id, CAST(:doc AS uuid), CAST(:kind AS varchar), CAST(:country AS varchar), 1, 'app', now()
            FROM users u WHERE u.country = CAST(:country AS varchar) AND u.email LIKE '%@example.com' AND u.role IN ('customer', 'driver', 'restaurant_owner')
            ON CONFLICT ON CONSTRAINT uq_legal_acceptances_user_document DO NOTHING"""),
            {"doc": doc_id, "kind": d["kind"], "country": d["country"]})
        n += 1
    return n
