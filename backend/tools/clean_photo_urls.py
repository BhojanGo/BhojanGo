"""One-off cleanup for the R22 security review (S13): dish photos (menu_items.image_url),
kitchen covers and logos (restaurants.cover_url, logo_url) that the API would refuse
today (core_api/modules/catalog/service/photo_urls.py): another site's image, a
`javascript:` or `data:` URL, an over-long string.

Dry run by default: lists each row it would clear (id, column, the first 80
characters) and changes nothing. With --apply it sets those values to NULL in one
transaction (the kitchen then shows its first dish photo or its cuisine's library
photo; the partner app asks for a new photo).

It refuses to run against QA or production (APP_ENV / RAILWAY_ENVIRONMENT_NAME)
unless --i-mean-this-environment is given, so nobody cleans a shared database by
accident. Run inside the core-api container, from its /srv (or backend/ on a checkout):

    python tools/clean_photo_urls.py            # list
    python tools/clean_photo_urls.py --apply    # clear them

The owner of an uploaded photo isn't checked here (only the address's shape): the
API checks that when a photo is saved.
"""
import argparse
import asyncio
import os
import sys
from collections.abc import Mapping
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PROTECTED = ("qa", "production", "prod")
COLUMNS = (("menu_items", "image_url"), ("restaurants", "cover_url"), ("restaurants", "logo_url"))


def environment_problem(env: Mapping[str, str], forced: bool) -> str | None:
    if forced:
        return None
    for var in ("APP_ENV", "RAILWAY_ENVIRONMENT_NAME"):
        if env.get(var, "").strip().lower() in PROTECTED:
            return (f"{var}={env[var]!r}: this is a shared environment. Take a backup, run it as a dry run first, "
                    "then add --i-mean-this-environment")
    return None


def bad(value: str | None) -> bool:
    """True when the API would refuse this value now (the shape check of photo_urls.check)."""
    from core_api.modules.catalog.service.photo_urls import shape_ok

    return not shape_ok(value)


async def run(apply: bool) -> int:
    from sqlalchemy import text

    from shared.db import AsyncSessionLocal

    found: list[tuple[str, str, str, str]] = []
    async with AsyncSessionLocal() as db:
        for table, column in COLUMNS:
            rows = (await db.execute(text(f"SELECT id, {column} FROM {table} WHERE {column} IS NOT NULL AND {column} <> ''"))).all()
            found += [(table, column, str(i), v) for i, v in rows if bad(v)]
        for table, column, i, v in found:
            print(f"{table}.{column} {i}: {v[:80]!r}")
        print(f"{len(found)} value(s) the API would refuse" + ("" if apply else " (dry run: nothing changed; --apply clears them)"))
        if apply and found:
            for table, column, i, _ in found:
                await db.execute(text(f"UPDATE {table} SET {column} = NULL WHERE id = CAST(:i AS uuid)"), {"i": i})
            await db.commit()
            print(f"cleared {len(found)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true", help="set the refused values to NULL (default: list only)")
    ap.add_argument("--i-mean-this-environment", dest="forced", action="store_true",
                    help="allow QA or production (after a backup and a dry run)")
    args = ap.parse_args(argv)
    problem = environment_problem(os.environ, args.forced)
    if problem:
        print(problem, file=sys.stderr)
        return 1
    return asyncio.run(run(args.apply))


if __name__ == "__main__":
    sys.exit(main())
