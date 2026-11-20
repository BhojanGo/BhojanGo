"""R22 caches without a database: the version-keyed map and the verified-token memo.
(The database half, the triggers and every edit showing at once: core_api/integration/test_r22_caches.py.)"""
import time
from types import SimpleNamespace

import pytest

from shared import auth, cache_versions
from shared.cache_versions import VersionedCache


def _db(wrote: bool = False):  # type: ignore[no-untyped-def]
    info = {cache_versions._WROTE: True} if wrote else {}
    return SimpleNamespace(sync_session=SimpleNamespace(info=info, new=set(), dirty=set(), deleted=set()))


def test_a_value_is_used_only_at_the_versions_it_was_read_at() -> None:
    c = VersionedCache("t1", ttl=60)
    db = _db()
    c.put(db, "k", (1, 2), "menu at 1.2")  # type: ignore[arg-type]
    assert c.get("k", (1, 2)) == "menu at 1.2"
    assert VersionedCache.is_miss(c.get("k", (1, 3))), "any newer version: computed again"
    assert VersionedCache.is_miss(c.get("other", (1, 2)))


def test_a_session_that_wrote_never_fills_it() -> None:
    c = VersionedCache("t2")
    c.put(_db(wrote=True), "k", (1,), "uncommitted")  # type: ignore[arg-type]
    assert VersionedCache.is_miss(c.get("k", (1,)))
    dirty = _db()
    dirty.sync_session.dirty = {object()}
    c.put(dirty, "k", (1,), "unflushed")  # type: ignore[arg-type]
    assert VersionedCache.is_miss(c.get("k", (1,)))


def test_backstop_lifetime_and_size() -> None:
    c = VersionedCache("t3", ttl=60, size=2)
    db = _db()
    c.put(db, "a", (1,), "a", ttl=0.01)  # type: ignore[arg-type]
    time.sleep(0.02)
    assert VersionedCache.is_miss(c.get("a", (1,)))
    for k in "bcd":
        c.put(db, k, (1,), k)  # type: ignore[arg-type]
    assert VersionedCache.is_miss(c.get("b", (1,))) and c.get("d", (1,)) == "d"


async def test_turned_off_it_always_computes(monkeypatch: pytest.MonkeyPatch) -> None:
    from shared.config import get_settings

    monkeypatch.setattr(get_settings(), "CACHE_VERSIONED", False)
    calls = []

    async def compute() -> int:
        calls.append(1)
        return len(calls)

    c = VersionedCache("t4")
    assert await c.through(_db(), "k", ("rules",), compute) == 1  # type: ignore[arg-type]
    assert await c.through(_db(), "k", ("rules",), compute) == 2  # type: ignore[arg-type]


def test_a_verified_token_is_remembered_but_still_expires_and_follows_its_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from shared import jwt_keys

    token = auth.encode_jwt({"sub": "u1", "type": "access", "exp": int(time.time()) + 60})
    assert auth.decode_jwt(token)["sub"] == "u1"
    assert token in auth._verified
    claims = auth.decode_jwt(token)
    claims["sub"] = "changed by a caller"
    assert auth.decode_jwt(token)["sub"] == "u1", "callers get a copy"

    # The key is retired: the remembered token fails at once.
    monkeypatch.setattr(jwt_keys, "verification_key", lambda kid: None)
    with pytest.raises(auth.InvalidTokenError):
        auth.decode_jwt(token)
    monkeypatch.undo()

    # Expired while remembered: refused.
    short = auth.encode_jwt({"sub": "u2", "type": "access", "exp": int(time.time()) + 1})
    assert auth.decode_jwt(short)["sub"] == "u2"
    assert short in auth._verified
    time.sleep(1.3)
    with pytest.raises(auth.InvalidTokenError):
        auth.decode_jwt(short)
    assert short not in auth._verified


def test_a_bad_token_is_never_remembered() -> None:
    with pytest.raises(auth.InvalidTokenError):
        auth.decode_jwt("not.a.token")
    assert "not.a.token" not in auth._verified


def test_processes_starting_together_share_one_dev_key(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R22: with several uvicorn processes, a second process must never replace the dev
    signing key the first one already uses (tokens would fail in the other process)."""
    from shared import jwt_keys
    from shared.config import get_settings

    monkeypatch.setattr(get_settings(), "JWT_DEV_KEY_PATH", str(tmp_path / "jwt-dev.pem"))
    first = jwt_keys._dev_key()
    second = jwt_keys._dev_key()  # as a process that started at the same moment would
    assert first.private_numbers() == second.private_numbers()
    assert [p.name for p in tmp_path.iterdir()] == ["jwt-dev.pem"]
