"""Round 8 D5 on Postgres + Redis: email sign-up with a verified address and
Argon2id, the lockout, reset links, linking, the audit log, and the seeded and
newly made admins' second step (enrolment, codes, recovery codes)."""
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from core_api.modules.identity.service import background, totp
from core_api.modules.identity.tests.signin import SEED_TOTP_SECRET, email_sign_up, finish, next_code

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)

PW = "Integration-pass-1"
ADMIN_PW = "BhojanGoAdmin1"


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    from core_api.main import app
    from shared.db import engine
    from shared.redis import close_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await background.drain()
    await close_redis()
    await engine.dispose()


def h(t: dict) -> dict:
    return {"Authorization": f"Bearer {t['access_token']}"}


def email(prefix: str) -> str:
    return f"{prefix}.{uuid.uuid4().hex[:10]}@example.com"


async def audit(user_id: str) -> list[str]:
    from shared.db import AsyncSessionLocal

    await background.drain()
    async with AsyncSessionLocal() as db:
        rows = await db.execute(text("SELECT action FROM audit_log WHERE entity_type = 'user' AND entity_id = :u ORDER BY at"),
                                {"u": user_id})
        return [r[0] for r in rows]


async def sql(q: str, **params):  # type: ignore[no-untyped-def]
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        return (await db.execute(text(q), params)).first()


async def test_sign_up_verifies_the_email_and_stores_argon2id(client: AsyncClient) -> None:
    address = email("signup")
    t = await email_sign_up(client, address, PW, country="IN", full_name="Asha Rao")
    assert t["is_new_user"] and t["user"]["is_verified"] and t["user"]["preferred_currency"] == "INR"
    row = await sql("SELECT hashed_password, password_changed_at FROM users WHERE email = :e", e=address)
    assert row[0].startswith("$argon2id$") and row[1] is not None
    r = await client.post("/api/v1/auth/login", json={"email": address, "password": PW})
    assert r.status_code == 200 and r.json()["mfa_required"] is False
    assert {"auth.signed_up", "auth.email_verified", "auth.password_set", "auth.sign_in"} <= set(await audit(t["user"]["id"]))


async def test_a_seeded_bcrypt_password_becomes_argon2id(client: AsyncClient) -> None:
    import bcrypt

    address = email("legacy")
    await email_sign_up(client, address, PW)
    legacy = bcrypt.hashpw(PW.encode(), bcrypt.gensalt(rounds=4)).decode()
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await db.execute(text("UPDATE users SET hashed_password = :h WHERE email = :e"), {"h": legacy, "e": address})
        await db.commit()
    assert (await client.post("/api/v1/auth/login", json={"email": address, "password": PW})).status_code == 200
    assert (await sql("SELECT hashed_password FROM users WHERE email = :e", e=address))[0].startswith("$argon2id$")


async def test_lockout_and_enumeration_safe_answers(client: AsyncClient) -> None:
    from core_api.modules.identity.api.v1.auth import limiter

    address = email("lock")
    t = await email_sign_up(client, address, PW)
    ghost = email("ghost")
    for who in (address, ghost):
        limiter.reset()
        codes = [(await client.post("/api/v1/auth/login", json={"email": who, "password": "Wrong-password-1"})).status_code
                 for _ in range(5)]
        assert codes == [401] * 4 + [429], (who, codes)
    limiter.reset()
    a = await client.post("/api/v1/auth/password/forgot", json={"email": address})
    b = await client.post("/api/v1/auth/password/forgot", json={"email": ghost})
    assert (a.status_code, a.json()) == (b.status_code, b.json()) == (202, a.json())
    assert (await audit(t["user"]["id"])).count("auth.locked") == 1


async def test_reset_link_on_redis_works_once(client: AsyncClient, monkeypatch) -> None:
    sent: list[dict] = []

    async def capture(channel, to, body, **kw):  # type: ignore[no-untyped-def]
        sent.append({"to": to, "body": body, **kw})
        return True

    monkeypatch.setattr("shared.notify.send", capture)
    address = email("reset")
    first = await email_sign_up(client, address, PW)
    await client.post("/api/v1/auth/password/forgot", json={"email": address})
    await background.drain()
    import re

    token = re.search(r"token=([\w-]+)", next(m["body"] for m in sent if m["to"] == address and "token=" in m["body"])).group(1)  # type: ignore[union-attr]
    r = await client.post("/api/v1/auth/password/reset", json={"token": token, "new_password": "Brand-new-pass-2"})
    assert r.status_code == 200, r.text
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})).status_code == 401
    assert (await client.post("/api/v1/auth/password/reset", json={"token": token, "new_password": "Other-new-pass-3"})).status_code == 400
    assert "auth.password_reset" in await audit(first["user"]["id"])


async def test_linking_a_phone_and_an_email_that_belong_to_others(client: AsyncClient) -> None:
    t = await email_sign_up(client, email("linker"), PW)
    r = await client.post("/api/v1/me/email", headers=h(t), json={"email": "customer1.hyd@example.com"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "EMAIL_IN_USE"
    r = await client.post("/api/v1/me/phone", headers=h(t), json={"phone": "+919000000101", "country": "IN"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "PHONE_IN_USE"
    phone = f"+9190000{uuid.uuid4().int % 100000:05d}"
    assert (await client.post("/api/v1/me/phone", headers=h(t), json={"phone": phone, "country": "IN"})).status_code == 202
    r = await client.post("/api/v1/me/phone/verify", headers=h(t), json={"phone": phone, "code": "123456"})
    assert r.status_code == 200 and r.json()["phone"] == phone
    assert "auth.phone_linked" in await audit(t["user"]["id"])


async def test_a_seeded_admin_needs_the_seed_key(client: AsyncClient) -> None:
    r = await client.post("/api/v1/auth/login", json={"email": "viewer@example.com", "password": ADMIN_PW})
    c = r.json()
    assert c["mfa_required"] and not c["enrolment_required"] and "access_token" not in c
    r = await client.post("/api/v1/auth/mfa/verify", json={"mfa_token": c["mfa_token"],
                                                         "code": await next_code("viewer@example.com", SEED_TOTP_SECRET)})
    assert r.status_code == 200, r.text
    assert (await client.get("/api/v1/admin/me", headers=h(r.json()))).status_code == 200
    row = await sql("SELECT totp_secret, totp_enabled_at FROM users WHERE email = 'viewer@example.com'")
    assert row[0] and SEED_TOTP_SECRET not in row[0] and row[1] is not None  # encrypted at rest


async def test_a_new_admin_enrols_then_uses_a_recovery_code(client: AsyncClient) -> None:
    address = email("newadmin")
    person = await email_sign_up(client, address, PW, country="IN")
    sup = await finish(client, "admin@example.com",
                       (await client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": ADMIN_PW})).json())
    r = await client.post("/api/v1/admin/role-assignments", headers=h(sup),
                          json={"user_id": person["user"]["id"], "role": "viewer", "scope": "IN"})
    assert r.status_code == 201, r.text
    # The customer session from before the role can't be refreshed into admin rights.
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": person["refresh_token"]})
    assert r.status_code == 401 and r.json()["detail"]["code"] == "MFA_REQUIRED"
    assert (await client.get("/api/v1/admin/me", headers=h(person))).status_code == 403

    c = (await client.post("/api/v1/auth/login", json={"email": address, "password": PW})).json()
    assert c["enrolment_required"] and c["email_code_sent"]
    start = (await client.post("/api/v1/auth/mfa/enrol/start", json={"mfa_token": c["mfa_token"], "email_code": "123456"})).json()
    step = totp.current_step()
    done = (await client.post("/api/v1/auth/mfa/enrol/confirm",
                              json={"mfa_token": c["mfa_token"], "code": totp.code_at(start["secret"], step)})).json()
    assert len(done["recovery_codes"]) == 10
    assert (await client.get("/api/v1/admin/me", headers=h(done))).status_code == 200
    assert (await sql("SELECT count(*) FROM recovery_codes WHERE user_id = :u AND used_at IS NULL", u=person["user"]["id"]))[0] == 10

    c = (await client.post("/api/v1/auth/login", json={"email": address, "password": PW})).json()
    r = await client.post("/api/v1/auth/mfa/recovery", json={"mfa_token": c["mfa_token"], "recovery_code": done["recovery_codes"][3]})
    assert r.status_code == 200, r.text
    assert (await sql("SELECT count(*) FROM recovery_codes WHERE user_id = :u AND used_at IS NULL", u=person["user"]["id"]))[0] == 9
    actions = await audit(person["user"]["id"])
    assert {"auth.mfa_enabled", "auth.mfa_used", "auth.mfa_recovery_used"} <= set(actions)
