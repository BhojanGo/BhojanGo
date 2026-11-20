"""In-process caches that are never stale after an edit (R22 performance).

The database keeps a version per scope (migration 0040_cache_versions): triggers on the
kitchen, menu, hours, market and rule tables add a row in the writing transaction, so a
new version is visible exactly when the edit commits, whoever made it (the API, the
worker, a script, psql). A cached value is stored under the versions read *before* it
was computed, and used only while those are still the current versions. So:

- every use costs one small query (the versions; ``versions``), and saves the queries,
  ORM loading and serialization behind the value;
- an edit is seen by the very next request in every process: no TTL to wait out;
- a value is never stored from a session that has written (its uncommitted changes
  could be in it), and a rolled-back edit's version is never reused (a sequence).

Scopes (migration 0040): ``kitchen:<restaurant id>``, ``kitchen:*`` (any kitchen),
``kitchens`` (bumped by every kitchen edit), ``markets``, ``rules``. Each cache also has
a backstop lifetime (``ttl``) and a size bound. ``CACHE_VERSIONED=0`` turns them all off.
"""
from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Hashable, Sequence
from typing import Any, TypeVar

from sqlalchemy import BigInteger, Column, MetaData, String, Table, event, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

T = TypeVar("T")

# Not on Base.metadata: the table is the migration's, and alembic check leaves it alone.
cache_versions = Table("cache_versions", MetaData(), Column("scope", String(80), primary_key=True),
                       Column("version", BigInteger, primary_key=True))

_WROTE = "cache_versions.wrote"
_MEMO = "cache_versions.memo"


@event.listens_for(Session, "after_flush")
def _after_flush(session: Session, _ctx: Any) -> None:
    session.info[_WROTE] = True
    session.info.pop(_MEMO, None)


@event.listens_for(Session, "do_orm_execute")
def _on_execute(state: Any) -> None:
    if not state.is_select:  # UPDATE, DELETE, INSERT, and text() of any kind (we can't tell)
        state.session.info[_WROTE] = True
        state.session.info.pop(_MEMO, None)


@event.listens_for(Session, "after_transaction_end")
def _after_transaction_end(session: Session, transaction: Any) -> None:
    if transaction.parent is None:
        session.info.pop(_WROTE, None)
        session.info.pop(_MEMO, None)


def enabled() -> bool:
    from shared.config import get_settings

    return get_settings().CACHE_VERSIONED


def wrote(db: AsyncSession) -> bool:
    """Has this session written (or does it hold changes not yet flushed)?"""
    s = db.sync_session
    return bool(s.info.get(_WROTE) or s.new or s.dirty or s.deleted)


async def versions(db: AsyncSession, scopes: Sequence[str]) -> tuple[int, ...]:
    """The current version of each scope (0: never edited), one query. Remembered
    for the rest of this transaction until the session writes."""
    memo: dict[str, int] = db.sync_session.info.setdefault(_MEMO, {})
    missing = [s for s in dict.fromkeys(scopes) if s not in memo]
    if missing:
        cols = [select(func.max(cache_versions.c.version)).where(cache_versions.c.scope == s).scalar_subquery()
                for s in missing]
        row = (await db.execute(select(*cols))).one()
        memo = db.sync_session.info.setdefault(_MEMO, {})
        memo.update({s: int(v or 0) for s, v in zip(missing, row)})
    return tuple(memo[s] for s in scopes)


_MISS = object()


class VersionedCache:
    """A bounded in-process map: key -> (versions, expires, value)."""

    caches: list[VersionedCache] = []

    def __init__(self, name: str, *, ttl: float = 300.0, size: int = 1024) -> None:
        self.name, self.ttl, self.size = name, ttl, size
        self._d: OrderedDict[Hashable, tuple[tuple[int, ...], float, Any]] = OrderedDict()
        self.hits = self.misses = 0
        VersionedCache.caches.append(self)

    def get(self, key: Hashable, ver: tuple[int, ...]) -> Any:
        e = self._d.get(key)
        if e is not None and e[0] == ver and e[1] > time.monotonic():
            self._d.move_to_end(key)
            self.hits += 1
            return e[2]
        self.misses += 1
        return _MISS

    def put(self, db: AsyncSession, key: Hashable, ver: tuple[int, ...], value: Any, ttl: float | None = None) -> None:
        if wrote(db):
            return
        self._d[key] = (ver, time.monotonic() + (self.ttl if ttl is None else ttl), value)
        self._d.move_to_end(key)
        while len(self._d) > self.size:
            self._d.popitem(last=False)

    def clear(self) -> None:
        self._d.clear()

    @staticmethod
    def is_miss(value: Any) -> bool:
        return value is _MISS

    async def through(self, db: AsyncSession, key: Hashable, scopes: Sequence[str],
                      compute: Callable[[], Awaitable[T]]) -> T:
        """The cached value for ``key`` at the scopes' current versions, else compute and keep it."""
        if not enabled():
            return await compute()
        ver = await versions(db, scopes)
        hit = self.get(key, ver)
        if hit is not _MISS:
            return hit  # type: ignore[no-any-return]
        value = await compute()
        self.put(db, key, ver, value)
        return value


def kitchen_scopes(restaurant_id: Any) -> tuple[str, str]:
    return f"kitchen:{restaurant_id}", "kitchen:*"
