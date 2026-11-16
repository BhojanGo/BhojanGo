"""Round 8 D5: email sign-up and sign-in, no account enumeration, the lockout,
password reset links, changing the password, linking an email or a phone, and
the admin second step (enrolment, codes, replay, recovery codes)."""
import re
import uuid

import bcrypt
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.models.admin_role import AdminRoleAssignment
from core_api.modules.identity.models.recovery_code import RecoveryCode
from core_api.modules.identity.models.user import User
from core_api.modules.identity.service import background, passwords, totp
from core_api.modules.identity.service.security import create_access_token, decode_token
from core_api.modules.identity.tests.signin import email_sign_up, finish, next_code

PW = "Long-enough-pass1"
NEW_PW = "Another-long-pass2"


def bearer(t: dict) -> dict:
    return {"Authorization": f"Bearer {t['access_token']}"}


def actions(audit_log: list, user_id=None) -> list[str]:  # type: ignore[no-untyped-def]
    return [a for uid, a, _ in audit_log if user_id is None or uid == user_id]


async def mails(outbox: list, to: str | None = None) -> list[dict]:
    await background.drain()
    return [m for m in outbox if m["channel"] == "email" and (to is None or m["to"] == to)]


async def make_user(db: AsyncSession, email: str | None, *, password: str | None = PW, phone: str | None = None,
                    roles: list[tuple[str, str]] = (), hashed: str | None = None, verified: bool = True) -> User:
    user = User(email=email, full_name="Test Person", phone=phone, role="admin" if roles else "customer", country="IN",
                hashed_password=hashed or (passwords.hash_password(password) if password else None), is_verified=verified)
    db.add(user)
    await db.flush()
    for r, s in roles:
        db.add(AdminRoleAssignment(user_id=user.id, role=r, scope=s))
    await db.flush()
    return user


def uniq(prefix: str, domain: str = "example.com") -> str:
    return f"{prefix}.{uuid.uuid4().hex[:8]}@{domain}"


# ── sign-up: the email is verified before the account exists ────────────────

async def test_sign_up_sends_a_code_and_creates_the_account_only_when_it_is_entered(client, db_session, outbox, audit_log) -> None:
    email = uniq("new", "bhojango.com")  # not a fixed-code domain: a random code
    r = await client.post("/api/v1/auth/email/sign-up", json={"email": email, "password": PW, "country": "IN",
                                                              "full_name": "Asha Rao", "language": "te"})
    assert r.status_code == 202, r.text
    assert (await db_session.execute(select(func.count()).select_from(User).where(User.email == email))).scalar() == 0
    [mail] = await mails(outbox, email)
    code = re.search(r"\b(\d{6})\b", mail["subject"]).group(1)  # type: ignore[union-attr]
    assert "BhojanGo" in mail["subject"] and code in mail["body"]
    assert "కోడ్" in mail["subject"]  # Telugu, as asked

    wrong = "000000" if code != "000000" else "111111"
    r = await client.post("/api/v1/auth/email/verify", json={"email": email, "code": wrong})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "CODE_INVALID"
    r = await client.post("/api/v1/auth/email/verify", json={"email": email, "code": code})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_new_user"] and body["user"]["is_verified"] and body["user"]["full_name"] == "Asha Rao"
    assert body["user"]["preferred_currency"] == "INR"
    user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    assert user.hashed_password.startswith("$argon2id$") and passwords.verify_password(PW, user.hashed_password)
    assert {"auth.signed_up", "auth.email_verified", "auth.password_set", "auth.sign_in"} <= set(actions(audit_log, user.id))
    # The code is used up.
    r = await client.post("/api/v1/auth/email/verify", json={"email": email, "code": code})
    assert r.status_code == 400
    assert any("Welcome" in m["subject"] or "స్వాగతం" in m["subject"] for m in await mails(outbox, email))


async def test_five_wrong_codes_burn_the_code(client, outbox) -> None:
    email = uniq("burn", "bhojango.com")
    await client.post("/api/v1/auth/email/sign-up", json={"email": email, "password": PW, "country": "US"})
    [mail] = await mails(outbox, email)
    code = re.search(r"\b(\d{6})\b", mail["subject"]).group(1)  # type: ignore[union-attr]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        assert (await client.post("/api/v1/auth/email/verify", json={"email": email, "code": wrong})).status_code == 400
    r = await client.post("/api/v1/auth/email/verify", json={"email": email, "code": code})
    assert r.status_code == 400


@pytest.mark.parametrize(("password", "code"), [("short-pw", "PASSWORD_TOO_SHORT"), ("password1234", "PASSWORD_BREACHED")])
async def test_sign_up_refuses_weak_passwords_with_a_code(client, password, code) -> None:
    r = await client.post("/api/v1/auth/email/sign-up", json={"email": uniq("weak"), "password": password, "country": "US"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == code


# ── no account enumeration ───────────────────────────────────────────────────

async def test_sign_up_code_and_forgot_answer_the_same_for_known_and_unknown_emails(client, db_session, outbox) -> None:
    known = uniq("known")
    await make_user(db_session, known)
    unknown = uniq("unknown")
    for path, extra in (("/auth/email/sign-up", {"password": PW, "country": "US"}), ("/auth/email/code", {}),
                        ("/auth/password/forgot", {})):
        a = await client.post(f"/api/v1{path}", json={"email": known, **extra})
        b = await client.post(f"/api/v1{path}", json={"email": unknown, **extra})
        assert (a.status_code, a.json()) == (b.status_code, b.json()), path
        assert a.status_code == 202
    # What differs is only the mail, which only the mailbox's owner reads.
    known_mail = [m["subject"] for m in await mails(outbox, known)]
    unknown_mail = [m["subject"] for m in await mails(outbox, unknown)]
    assert "You already have a BhojanGo account" in known_mail
    assert any("password" in s.lower() for s in known_mail)
    assert len(unknown_mail) == 1 and "code" in unknown_mail[0]  # the sign-up code only


async def test_sign_up_hashes_the_password_for_an_existing_email_too(client, db_session, monkeypatch) -> None:
    known = uniq("known")
    await make_user(db_session, known)
    calls: list[str] = []
    real = passwords.hash_password
    monkeypatch.setattr(passwords, "hash_password", lambda pw: calls.append(pw) or real(pw))
    await client.post("/api/v1/auth/email/sign-up", json={"email": known, "password": PW, "country": "US"})
    await client.post("/api/v1/auth/email/sign-up", json={"email": uniq("fresh"), "password": PW, "country": "US"})
    assert len(calls) == 2


async def test_wrong_password_and_unknown_email_do_the_same_work(client, db_session, monkeypatch) -> None:
    known = uniq("known")
    await make_user(db_session, known)
    checked: list[str] = []
    real = passwords.verify_password
    monkeypatch.setattr(passwords, "verify_password", lambda pw, h: checked.append(h) or real(pw, h))
    a = await client.post("/api/v1/auth/login", json={"email": known, "password": "Wrong-password-9"})
    b = await client.post("/api/v1/auth/login", json={"email": uniq("ghost"), "password": "Wrong-password-9"})
    assert (a.status_code, a.json()) == (b.status_code, b.json()) == (401, a.json())
    assert len(checked) == 2 and checked[1] == passwords.DUMMY_HASH


async def test_per_email_limit_applies_to_unknown_emails_too(client, db_session) -> None:
    known, unknown = uniq("known"), uniq("unknown")
    await make_user(db_session, known)
    from core_api.modules.identity.api.v1.auth import limiter

    for email in (known, unknown):
        statuses = []
        for _ in range(6):
            limiter.reset()  # the per-IP limit is not what this tests
            statuses.append((await client.post("/api/v1/auth/email/code", json={"email": email})).status_code)
        assert statuses == [202] * 5 + [429], (email, statuses)


# ── sign in with a code ──────────────────────────────────────────────────────

async def test_email_me_a_code_signs_in_and_verifies_the_email(client, db_session, outbox, audit_log) -> None:
    email = uniq("codein")
    user = await make_user(db_session, email, password=None, verified=False)
    assert (await client.post("/api/v1/auth/email/code", json={"email": email})).status_code == 202
    assert len(await mails(outbox, email)) == 1
    r = await client.post("/api/v1/auth/email/verify", json={"email": email, "code": "123456"})
    assert r.status_code == 200 and r.json()["user"]["id"] == str(user.id) and not r.json()["is_new_user"]
    assert r.json()["user"]["is_verified"] is True
    assert ("auth.sign_in" in actions(audit_log, user.id)) and ("auth.email_verified" in actions(audit_log, user.id))
    # No code was sent to an unknown email, so nothing can be verified there.
    r = await client.post("/api/v1/auth/email/verify", json={"email": uniq("ghost"), "code": "123456"})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "CODE_INVALID"


# ── lockout ──────────────────────────────────────────────────────────────────

async def test_five_wrong_passwords_lock_for_fifteen_minutes(client, db_session, audit_log) -> None:
    from core_api.modules.identity.api.v1.auth import limiter

    email = uniq("lock")
    user = await make_user(db_session, email)
    codes = []
    for _ in range(5):
        r = await client.post("/api/v1/auth/login", json={"email": email, "password": "Wrong-password-1"})
        codes.append(r.status_code)
    assert codes == [401, 401, 401, 401, 429]
    detail = r.json()["detail"]
    assert detail["code"] == "ACCOUNT_LOCKED" and 890 <= detail["retry_after"] <= 900
    assert "15 minutes" in detail["message"] and r.headers["Retry-After"]
    limiter.reset()
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": PW})  # even the right one
    assert r.status_code == 429
    assert actions(audit_log, user.id).count("auth.sign_in_failed") == 5
    assert actions(audit_log, user.id).count("auth.locked") == 1

    # An email code proves the mailbox: it still works and lifts the lock.
    await client.post("/api/v1/auth/email/code", json={"email": email})
    assert (await client.post("/api/v1/auth/email/verify", json={"email": email, "code": "123456"})).status_code == 200
    assert (await client.post("/api/v1/auth/login", json={"email": email, "password": PW})).status_code == 200


async def test_an_unknown_email_locks_exactly_like_an_account(client) -> None:
    ghost = uniq("ghost")
    answers = [await client.post("/api/v1/auth/login", json={"email": ghost, "password": "Wrong-password-1"})
               for _ in range(5)]
    assert [a.status_code for a in answers] == [401, 401, 401, 401, 429]
    assert answers[-1].json()["detail"]["code"] == "ACCOUNT_LOCKED"


async def test_a_right_password_resets_the_count(client, db_session) -> None:
    email = uniq("reset")
    await make_user(db_session, email)
    for _ in range(4):
        await client.post("/api/v1/auth/login", json={"email": email, "password": "Wrong-password-1"})
    assert (await client.post("/api/v1/auth/login", json={"email": email, "password": PW})).status_code == 200
    from core_api.modules.identity.api.v1.auth import limiter

    limiter.reset()
    for _ in range(4):
        r = await client.post("/api/v1/auth/login", json={"email": email, "password": "Wrong-password-1"})
    assert r.status_code == 401


async def test_the_lock_ends_after_its_time(client, db_session) -> None:
    from core_api.modules.identity.service.guard import ident_hash

    email = uniq("ttl")
    await make_user(db_session, email)
    for _ in range(5):
        await client.post("/api/v1/auth/login", json={"email": email, "password": "Wrong-password-1"})
    key = f"pw_lock:{ident_hash(email)}"
    assert 890 <= await client.redis.ttl(key) <= 900
    await client.redis.delete(key)  # = 15 minutes later
    from core_api.modules.identity.api.v1.auth import limiter

    limiter.reset()
    assert (await client.post("/api/v1/auth/login", json={"email": email, "password": PW})).status_code == 200


# ── bcrypt -> Argon2id on the next sign-in ───────────────────────────────────

async def test_a_bcrypt_password_is_rehashed_on_sign_in(client, db_session) -> None:
    email = uniq("legacy")
    legacy = bcrypt.hashpw(b"BhojanGo123", bcrypt.gensalt(rounds=4)).decode()
    user = await make_user(db_session, email, hashed=legacy)
    assert (await client.post("/api/v1/auth/login", json={"email": email, "password": "BhojanGo123"})).status_code == 200
    await db_session.refresh(user)
    assert user.hashed_password.startswith("$argon2id$") and passwords.verify_password("BhojanGo123", user.hashed_password)


# ── forgot password: a single-use link for 30 minutes ───────────────────────

async def _reset_token(outbox: list, email: str) -> str:
    [mail] = [m for m in await mails(outbox, email) if "new" in m["subject"].lower() and "password" in m["subject"].lower()]
    return re.search(r"/signin/reset\?token=([\w-]+)", mail["body"]).group(1)  # type: ignore[union-attr]


async def test_reset_link_works_once_signs_out_everywhere_and_is_audited(client, db_session, outbox, audit_log) -> None:
    email = uniq("forgot")
    user = await make_user(db_session, email)
    session = (await client.post("/api/v1/auth/login", json={"email": email, "password": PW})).json()
    await client.post("/api/v1/auth/password/forgot", json={"email": email})
    token = await _reset_token(outbox, email)

    # Stored hashed, for 30 minutes.
    keys = [k async for k in client.redis.scan_iter("pwreset:*")]
    assert keys and all(token not in k for k in keys)
    for k in keys:
        assert token not in (await client.redis.get(k) or "")
    assert 1790 <= await client.redis.ttl(keys[0]) <= 1800

    assert (await client.post("/api/v1/auth/password/reset/check", json={"token": token})).json() == {"valid": True}
    r = await client.post("/api/v1/auth/password/reset", json={"token": token, "new_password": "short"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "PASSWORD_TOO_SHORT"
    r = await client.post("/api/v1/auth/password/reset", json={"token": token, "new_password": NEW_PW})
    assert r.status_code == 200, r.text  # a rejected password didn't use the link up

    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": session["refresh_token"]})).status_code == 401
    assert (await client.post("/api/v1/auth/login", json={"email": email, "password": PW})).status_code == 401
    assert (await client.post("/api/v1/auth/login", json={"email": email, "password": NEW_PW})).status_code == 200
    again = await client.post("/api/v1/auth/password/reset", json={"token": token, "new_password": NEW_PW + "x"})
    assert again.status_code == 400 and again.json()["detail"]["code"] == "RESET_LINK_INVALID"
    assert (await client.post("/api/v1/auth/password/reset/check", json={"token": token})).json() == {"valid": False}
    assert "auth.password_reset" in actions(audit_log, user.id)
    assert any("changed" in m["subject"] for m in await mails(outbox, email))


async def test_an_expired_or_replaced_link_does_not_work(client, db_session, outbox) -> None:
    from core_api.modules.identity.api.v1.auth import limiter

    email = uniq("expired")
    await make_user(db_session, email)
    await client.post("/api/v1/auth/password/forgot", json={"email": email})
    first = await _reset_token(outbox, email)
    outbox.clear()
    limiter.reset()
    await client.post("/api/v1/auth/password/forgot", json={"email": email})
    second = await _reset_token(outbox, email)
    r = await client.post("/api/v1/auth/password/reset", json={"token": first, "new_password": NEW_PW})
    assert r.status_code == 400  # a newer link ends the older one
    async for k in client.redis.scan_iter("pwreset:*"):
        await client.redis.delete(k)  # = 30 minutes later
    r = await client.post("/api/v1/auth/password/reset", json={"token": second, "new_password": NEW_PW})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "RESET_LINK_INVALID"


# ── change password, link email / phone ──────────────────────────────────────

async def test_change_password_needs_the_current_one_and_signs_out_other_devices(client, db_session, outbox, audit_log) -> None:
    email = uniq("change")
    user = await make_user(db_session, email)
    laptop = (await client.post("/api/v1/auth/login", json={"email": email, "password": PW})).json()
    phone = (await client.post("/api/v1/auth/login", json={"email": email, "password": PW})).json()

    r = await client.post("/api/v1/me/password", headers=bearer(laptop), json={"current_password": "nope-nope-nope",
                                                                              "new_password": NEW_PW})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "WRONG_PASSWORD"
    r = await client.post("/api/v1/me/password", headers=bearer(laptop), json={"current_password": PW,
                                                                              "new_password": "password1234"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "PASSWORD_BREACHED"
    r = await client.post("/api/v1/me/password", headers=bearer(laptop), json={"current_password": PW, "new_password": NEW_PW})
    assert r.status_code == 200, r.text
    fresh = r.json()
    assert (await client.get("/api/v1/users/me", headers=bearer(fresh))).status_code == 200
    assert (await client.get("/api/v1/users/me", headers=bearer(laptop))).status_code == 401  # the old token
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": phone["refresh_token"]})).status_code == 401
    assert "auth.password_changed" in actions(audit_log, user.id)
    assert any("changed" in m["subject"] for m in await mails(outbox, email))


async def test_a_phone_account_sets_a_first_password_after_linking_an_email(client, db_session, audit_log) -> None:
    await client.post("/api/v1/auth/send-otp", json={"phone": "+9190000555", "country": "IN"})
    t = (await client.post("/api/v1/auth/phone", json={"phone": "+9190000555", "otp": "123456", "country": "IN"})).json()
    r = await client.post("/api/v1/me/password", headers=bearer(t), json={"new_password": NEW_PW})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "EMAIL_REQUIRED"

    email = uniq("linked")
    assert (await client.post("/api/v1/me/email", headers=bearer(t), json={"email": email})).status_code == 202
    r = await client.post("/api/v1/me/email/verify", headers=bearer(t), json={"email": email, "code": "000000"})
    assert r.status_code == 400
    r = await client.post("/api/v1/me/email/verify", headers=bearer(t), json={"email": email, "code": "123456"})
    assert r.status_code == 200 and r.json()["email"] == email and r.json()["is_verified"]
    sec = (await client.get("/api/v1/me/security", headers=bearer(t))).json()
    assert sec["email_verified"] and sec["phone_verified"] and not sec["has_password"]

    r = await client.post("/api/v1/me/password", headers=bearer(t), json={"new_password": NEW_PW})
    assert r.status_code == 200, r.text
    uid = uuid.UUID(t["user"]["id"])
    assert {"auth.email_linked", "auth.password_set"} <= set(actions(audit_log, uid))
    assert (await client.post("/api/v1/auth/login", json={"email": email, "password": NEW_PW})).status_code == 200


async def test_an_email_or_phone_on_another_account_cannot_be_linked(client, db_session) -> None:
    taken_email = uniq("taken")
    await make_user(db_session, taken_email, phone="+9190000666")
    me = uniq("me")
    await make_user(db_session, me)
    t = (await client.post("/api/v1/auth/login", json={"email": me, "password": PW})).json()
    r = await client.post("/api/v1/me/email", headers=bearer(t), json={"email": taken_email.upper()})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "EMAIL_IN_USE"
    assert taken_email not in r.text and "Test Person" not in r.text
    r = await client.post("/api/v1/me/phone", headers=bearer(t), json={"phone": "+9190000666", "country": "IN"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "PHONE_IN_USE"
    # A free number links with its SMS code.
    assert (await client.post("/api/v1/me/phone", headers=bearer(t), json={"phone": "+9190000667", "country": "IN"})).status_code == 202
    r = await client.post("/api/v1/me/phone/verify", headers=bearer(t), json={"phone": "+9190000667", "code": "123456"})
    assert r.status_code == 200 and r.json()["phone"] == "+9190000667" and r.json()["is_phone_verified"]


async def test_replacing_an_email_tells_the_old_address(client, db_session, outbox) -> None:
    old = uniq("old")
    await make_user(db_session, old)
    t = (await client.post("/api/v1/auth/login", json={"email": old, "password": PW})).json()
    new = uniq("new")
    await client.post("/api/v1/me/email", headers=bearer(t), json={"email": new})
    assert (await client.post("/api/v1/me/email/verify", headers=bearer(t), json={"email": new, "code": "123456"})).status_code == 200
    assert any("changed" in m["subject"] for m in await mails(outbox, old))


async def test_google_link_to_an_unverified_account_drops_its_password(client, db_session, monkeypatch) -> None:
    from core_api.modules.identity.service import oidc

    email = uniq("prehijack")
    user = await make_user(db_session, email, verified=False)

    async def fake_verify(provider, token, audiences):  # type: ignore[no-untyped-def]
        return oidc.Identity(subject="g-123", email=email, email_verified=True, name="Real Owner")

    monkeypatch.setattr(oidc, "verify", fake_verify)
    from shared.config import get_settings

    monkeypatch.setattr(get_settings().identity, "GOOGLE_CLIENT_ID", "web-client")
    r = await client.post("/api/v1/auth/social-login", json={"provider": "google", "token": "x" * 20, "country": "IN"})
    assert r.status_code == 200, r.text
    await db_session.refresh(user)
    assert user.google_id == "g-123" and user.is_verified and user.hashed_password is None


# ── admins: the second step ──────────────────────────────────────────────────

async def _admin(db_session) -> tuple[str, User]:  # type: ignore[no-untyped-def]
    email = uniq("ops")
    return email, await make_user(db_session, email, roles=[("city_ops", "IN-TG-HYD")])


async def test_an_admin_password_alone_gets_no_tokens(client, db_session) -> None:
    email, _ = await _admin(db_session)
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": PW})
    body = r.json()
    assert r.status_code == 200 and body["mfa_required"] is True and "access_token" not in body
    assert body["enrolment_required"] is True and body["email_code_sent"] is True and body["expires_in"] == 600


async def test_enrolment_needs_the_emailed_code_then_a_code_from_the_app(client, db_session, outbox, audit_log) -> None:
    email, user = await _admin(db_session)
    challenge = (await client.post("/api/v1/auth/login", json={"email": email, "password": PW})).json()
    token = challenge["mfa_token"]
    assert len(await mails(outbox, email)) == 1
    r = await client.post("/api/v1/auth/mfa/enrol/start", json={"mfa_token": token, "email_code": "000000"})
    assert r.status_code == 400
    r = await client.post("/api/v1/auth/mfa/enrol/start", json={"mfa_token": token, "email_code": "123456"})
    assert r.status_code == 200, r.text
    start = r.json()
    assert start["account"] == email and start["qr_svg"].startswith("data:image/svg+xml;base64,")
    assert start["otpauth_uri"].startswith("otpauth://totp/BhojanGo") and start["secret"] in start["otpauth_uri"]
    # Asking again shows the same key (no new email code needed).
    again = await client.post("/api/v1/auth/mfa/enrol/start", json={"mfa_token": token, "email_code": "000000"})
    assert again.json()["secret"] == start["secret"]

    secret = start["secret"]
    step = totp.current_step()
    bad = await client.post("/api/v1/auth/mfa/enrol/confirm", json={"mfa_token": token, "code": totp.code_at(secret, step + 5)})
    assert bad.status_code == 400
    r = await client.post("/api/v1/auth/mfa/enrol/confirm", json={"mfa_token": token, "code": totp.code_at(secret, step)})
    assert r.status_code == 200, r.text
    done = r.json()
    assert len(done["recovery_codes"]) == 10 and done["admin_roles"] == ["city_ops@IN-TG-HYD"]
    claims = decode_token(done["access_token"])
    assert claims["mfa"] is True and claims["adm"] == ["city_ops@IN-TG-HYD"]
    assert (await client.get("/api/v1/admin/me", headers=bearer(done))).status_code == 200
    await db_session.refresh(user)
    assert user.totp_secret and secret not in user.totp_secret and user.totp_enabled_at  # stored encrypted
    stored = (await db_session.execute(select(RecoveryCode.code_hash).where(RecoveryCode.user_id == user.id))).scalars().all()
    assert len(stored) == 10 and not set(done["recovery_codes"]) & set(stored)
    assert "auth.mfa_enabled" in actions(audit_log, user.id)
    # The challenge is gone once used.
    r = await client.post("/api/v1/auth/mfa/verify", json={"mfa_token": token, "code": totp.code_at(secret, step + 1)})
    assert r.status_code == 401 and r.json()["detail"]["code"] == "MFA_EXPIRED"


async def _enrolled(client, db_session) -> tuple[str, User, str, list[str]]:  # type: ignore[no-untyped-def]
    email, user = await _admin(db_session)
    body = (await client.post("/api/v1/auth/login", json={"email": email, "password": PW})).json()
    done = await finish(client, email, body)
    from core_api.modules.identity.tests.signin import secrets_by_email

    return email, user, secrets_by_email[email], done["recovery_codes"]


async def test_codes_sign_in_but_never_twice(client, db_session, audit_log) -> None:
    email, user, secret, _ = await _enrolled(client, db_session)
    c1 = (await client.post("/api/v1/auth/login", json={"email": email, "password": PW})).json()
    assert c1["enrolment_required"] is False and c1["email_code_sent"] is False
    code = await next_code(email, secret)
    r = await client.post("/api/v1/auth/mfa/verify", json={"mfa_token": c1["mfa_token"], "code": code})
    assert r.status_code == 200 and decode_token(r.json()["access_token"])["mfa"] is True
    assert "auth.mfa_used" in actions(audit_log, user.id)
    c2 = (await client.post("/api/v1/auth/login", json={"email": email, "password": PW})).json()
    r = await client.post("/api/v1/auth/mfa/verify", json={"mfa_token": c2["mfa_token"], "code": code})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "CODE_INVALID"  # replayed


async def test_recovery_codes_work_once_each(client, db_session, audit_log) -> None:
    email, user, _, codes = await _enrolled(client, db_session)
    c = (await client.post("/api/v1/auth/login", json={"email": email, "password": PW})).json()
    r = await client.post("/api/v1/auth/mfa/recovery", json={"mfa_token": c["mfa_token"], "recovery_code": codes[0].lower()})
    assert r.status_code == 200, r.text
    assert "auth.mfa_recovery_used" in actions(audit_log, user.id)
    sec = (await client.get("/api/v1/me/security", headers=bearer(r.json()))).json()
    assert sec["mfa_enabled"] and sec["mfa_required"] and sec["recovery_codes_left"] == 9
    c = (await client.post("/api/v1/auth/login", json={"email": email, "password": PW})).json()
    r = await client.post("/api/v1/auth/mfa/recovery", json={"mfa_token": c["mfa_token"], "recovery_code": codes[0]})
    assert r.status_code == 400


async def test_wrong_codes_end_the_challenge_and_count_towards_the_lock(client, db_session, audit_log) -> None:
    email, user, secret, _ = await _enrolled(client, db_session)
    c = (await client.post("/api/v1/auth/login", json={"email": email, "password": PW})).json()
    wrong = totp.code_at(secret, totp.current_step() + 7)
    statuses = [(await client.post("/api/v1/auth/mfa/verify", json={"mfa_token": c["mfa_token"], "code": wrong})).status_code
                for _ in range(5)]
    assert statuses == [400, 400, 400, 400, 429]  # the fifth wrong code also locks the account
    assert "auth.locked" in actions(audit_log, user.id)
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 429


async def test_renewing_recovery_codes_needs_an_app_code(client, db_session) -> None:
    email, _, secret, old = await _enrolled(client, db_session)
    c = (await client.post("/api/v1/auth/login", json={"email": email, "password": PW})).json()
    t = (await client.post("/api/v1/auth/mfa/verify", json={"mfa_token": c["mfa_token"],
                                                          "code": await next_code(email, secret)})).json()
    assert (await client.post("/api/v1/me/mfa/recovery-codes", headers=bearer(t), json={"code": "000000"})).status_code == 400
    r = await client.post("/api/v1/me/mfa/recovery-codes", headers=bearer(t), json={"code": await next_code(email, secret)})
    assert r.status_code == 200 and len(r.json()["recovery_codes"]) == 10 and not set(r.json()["recovery_codes"]) & set(old)


async def test_admin_rights_need_a_second_step_token(client, db_session) -> None:
    email, user = await _admin(db_session)
    # A token made without the second step (e.g. from before this shipped) carries no rights.
    token, _ = create_access_token(str(user.id), email, "admin", "IN", ["city_ops@IN-TG-HYD"], mfa=False)
    claims = decode_token(token)
    assert "adm" not in claims and "mfa" not in claims
    r = await client.get("/api/v1/admin/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
    # ...and its refresh token can't be refreshed into one.
    from core_api.modules.identity.service.security import create_refresh_token

    refresh, jti, family, ttl = create_refresh_token(str(user.id))
    await client.redis.setex(f"refresh_family:{user.id}:{family}", ttl, jti)
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 401 and r.json()["detail"]["code"] == "MFA_REQUIRED"


async def test_phone_and_email_code_sign_in_also_ask_admins_for_the_second_step(client, db_session) -> None:
    email = uniq("ops")
    await make_user(db_session, email, phone="+9190000777", roles=[("viewer", "IN")])
    await client.post("/api/v1/auth/send-otp", json={"phone": "+9190000777", "country": "IN"})
    r = await client.post("/api/v1/auth/phone", json={"phone": "+9190000777", "otp": "123456", "country": "IN"})
    assert r.json()["mfa_required"] is True and "access_token" not in r.json()
    await client.post("/api/v1/auth/email/code", json={"email": email})
    r = await client.post("/api/v1/auth/email/verify", json={"email": email, "code": "123456"})
    assert r.json()["mfa_required"] is True and "access_token" not in r.json()


async def test_customers_never_see_the_second_step(client, db_session) -> None:
    email = uniq("cust")
    await make_user(db_session, email)
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": PW})
    assert r.json()["mfa_required"] is False and r.json()["access_token"]
    assert "mfa" not in decode_token(r.json()["access_token"])


async def test_email_sign_up_with_an_example_address_uses_the_fixed_code(client) -> None:
    data = await email_sign_up(client, uniq("qa"))
    assert data["is_new_user"]
