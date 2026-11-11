"""P5: RS256 + JWKS, rotating refresh tokens, phone OTP sign-in, Apple/Google,
account deletion, and the admin roles API with scopes."""
import time
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.models.address import Address
from core_api.modules.identity.models.admin_role import AdminRoleAssignment
from core_api.modules.identity.models.user import User
from core_api.modules.identity.service import oidc
from core_api.modules.identity.service.security import hash_password
from shared import jwt_keys
from shared.auth import InvalidTokenError, decode_access_token

PASSWORD = "Passw0rdX"
SEED_PHONE_IN = "+9190000777"   # seed prefix: fixed OTP 123456 outside production


async def make_user(db: AsyncSession, email: str | None, country: str = "IN", role: str = "customer",
                    phone: str | None = None, assignments: list[tuple[str, str]] = ()) -> User:
    user = User(email=email, full_name=email or "User", hashed_password=hash_password(PASSWORD), role=role,
                country=country, phone=phone)
    db.add(user)
    await db.flush()
    for r, s in assignments:
        db.add(AdminRoleAssignment(user_id=user.id, role=r, scope=s))
    await db.flush()
    return user


async def login(client: AsyncClient, email: str) -> dict:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()


def bearer(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


# ── RS256 + JWKS ──────────────────────────────────────────────────────────────

async def test_tokens_are_rs256_and_verifiable_with_jwks(client: AsyncClient, db_session) -> None:
    await make_user(db_session, "rs@example.com")
    tokens = await login(client, "rs@example.com")
    header = jwt.get_unverified_header(tokens["access_token"])
    assert header["alg"] == "RS256"

    jwks = (await client.get("/.well-known/jwks.json")).json()
    key = next(k for k in jwks["keys"] if k["kid"] == header["kid"])
    assert key["kty"] == "RSA" and "d" not in key  # public part only
    pub = jwt.algorithms.RSAAlgorithm.from_jwk(key)
    claims = jwt.decode(tokens["access_token"], pub, algorithms=["RS256"], audience="bhojango", issuer="bhojango")
    assert claims["type"] == "access"
    assert claims["exp"] - claims["iat"] == 15 * 60
    assert (await client.get("/api/v1/auth/jwks")).json() == jwks


async def test_forged_and_downgraded_tokens_are_rejected(client: AsyncClient, db_session) -> None:
    user = await make_user(db_session, "forge@example.com")
    claims = {"sub": str(user.id), "type": "access", "role": "admin", "country": "IN", "iss": "bhojango",
              "aud": "bhojango", "exp": datetime.now(UTC) + timedelta(minutes=5)}
    _, kid = jwt_keys.signing_key()
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = jwt.encode(claims, other, algorithm="RS256", headers={"kid": kid})
    hs256 = jwt.encode(claims, "guess", algorithm="HS256", headers={"kid": kid})
    for token in (forged, hs256, "not.a.jwt"):
        with pytest.raises(InvalidTokenError):
            decode_access_token(token)
        r = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


# ── Rotating refresh tokens ───────────────────────────────────────────────────

async def test_refresh_rotates_and_reuse_revokes_the_session(client: AsyncClient, db_session) -> None:
    await make_user(db_session, "rot@example.com")
    first = await login(client, "rot@example.com")

    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert r.status_code == 200, r.text
    second = r.json()
    assert second["refresh_token"] != first["refresh_token"]

    # The old token again: someone copied it. Both copies stop working.
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert r.status_code == 401 and r.json()["detail"]["code"] == "TOKEN_REUSED"
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": second["refresh_token"]})
    assert r.status_code == 401 and r.json()["detail"]["code"] == "TOKEN_REVOKED"


async def test_sessions_are_independent_and_logout_ends_all(client: AsyncClient, db_session) -> None:
    await make_user(db_session, "two@example.com")
    phone_session = await login(client, "two@example.com")
    web_session = await login(client, "two@example.com")
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": phone_session["refresh_token"]})).status_code == 200

    r = await client.post("/api/v1/auth/logout", headers=bearer(web_session))
    assert r.status_code == 200
    assert (await client.get("/api/v1/users/me", headers=bearer(web_session))).status_code == 401
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": web_session["refresh_token"]})
    assert r.status_code == 401


async def test_access_token_cannot_be_used_to_refresh(client: AsyncClient, db_session) -> None:
    await make_user(db_session, "type@example.com")
    t = await login(client, "type@example.com")
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": t["access_token"]})
    assert r.status_code == 401


# ── Phone OTP sign-in ─────────────────────────────────────────────────────────

async def test_phone_sign_in_creates_then_signs_in(client: AsyncClient) -> None:
    assert (await client.post("/api/v1/auth/send-otp", json={"phone": SEED_PHONE_IN, "country": "IN"})).status_code == 200
    r = await client.post("/api/v1/auth/phone", json={"phone": SEED_PHONE_IN, "otp": "123456", "country": "IN",
                                                      "full_name": "Asha Rao"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_new_user"] is True
    assert body["user"]["email"] is None
    assert body["user"]["is_phone_verified"] is True
    assert body["user"]["preferred_currency"] == "INR"

    await client.post("/api/v1/auth/send-otp", json={"phone": SEED_PHONE_IN, "country": "IN"})
    r = await client.post("/api/v1/auth/phone", json={"phone": SEED_PHONE_IN, "otp": "123456", "country": "IN"})
    assert r.json()["is_new_user"] is False
    assert r.json()["user"]["id"] == body["user"]["id"]


async def test_phone_sign_in_wrong_or_reused_code(client: AsyncClient) -> None:
    phone = "+9190000778"
    await client.post("/api/v1/auth/send-otp", json={"phone": phone, "country": "IN"})
    r = await client.post("/api/v1/auth/phone", json={"phone": phone, "otp": "000000", "country": "IN"})
    assert r.status_code == 400
    assert (await client.post("/api/v1/auth/phone", json={"phone": phone, "otp": "123456", "country": "IN"})).status_code == 200
    # Codes are single use.
    r = await client.post("/api/v1/auth/phone", json={"phone": phone, "otp": "123456", "country": "IN"})
    assert r.status_code == 400


async def test_non_seed_phone_gets_a_random_code(client: AsyncClient, capsys) -> None:
    phone = "+919876543210"
    await client.post("/api/v1/auth/send-otp", json={"phone": phone, "country": "IN"})
    out = capsys.readouterr().out
    code = out.split("verification code is: ")[1][:6]
    assert code.isdigit()
    r = await client.post("/api/v1/auth/phone", json={"phone": phone, "otp": code, "country": "IN"})
    assert r.status_code == 200


# ── Sign in with Apple / Google ───────────────────────────────────────────────

PROVIDER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PROVIDER_KID = "test-kid"


def id_token(provider: str, sub: str, *, email: str | None = None, verified: bool | str = True,
             aud: str = "com.bhojango.app", key=PROVIDER_KEY, name: str | None = None) -> str:
    iss = {"apple": "https://appleid.apple.com", "google": "https://accounts.google.com"}[provider]
    now = int(time.time())
    claims = {"iss": iss, "aud": aud, "sub": sub, "iat": now, "exp": now + 600, "email_verified": verified}
    if email:
        claims["email"] = email
    if name:
        claims["name"] = name
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": PROVIDER_KID})


@pytest.fixture
def provider_keys(monkeypatch):
    async def keys(provider, *, refresh=False):
        return {PROVIDER_KID: PROVIDER_KEY.public_key()}

    monkeypatch.setattr(oidc, "_keys", keys)
    from shared.config import get_settings

    monkeypatch.setattr(get_settings().identity, "GOOGLE_CLIENT_IDS", ["google-web-client"])


async def test_apple_sign_in_creates_account(client: AsyncClient, provider_keys) -> None:
    token = id_token("apple", "apple-001", email="a1@privaterelay.appleid.com", verified="true")
    r = await client.post("/api/v1/auth/social-login", json={"provider": "apple", "token": token, "country": "US"})
    assert r.status_code == 200, r.text
    assert r.json()["is_new_user"] is True
    again = await client.post("/api/v1/auth/social-login", json={"provider": "apple", "token": token, "country": "US"})
    assert again.json()["user"]["id"] == r.json()["user"]["id"]
    assert again.json()["is_new_user"] is False


async def test_forged_apple_token_is_rejected(client: AsyncClient, provider_keys) -> None:
    attacker = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = id_token("apple", "victim", email="victim@example.com", key=attacker)
    r = await client.post("/api/v1/auth/social-login", json={"provider": "apple", "token": forged})
    assert r.status_code == 401
    wrong_aud = id_token("apple", "x", aud="com.someone.else")
    assert (await client.post("/api/v1/auth/social-login", json={"provider": "apple", "token": wrong_aud})).status_code == 401


async def test_google_links_only_verified_email(client: AsyncClient, db_session, provider_keys) -> None:
    existing = await make_user(db_session, "owner@example.com", country="US")
    unverified = id_token("google", "g-attacker", email="owner@example.com", verified=False, aud="google-web-client")
    r = await client.post("/api/v1/auth/social-login", json={"provider": "google", "token": unverified})
    assert r.status_code == 200
    assert r.json()["user"]["id"] != str(existing.id)  # not linked: separate account, no email

    verified = id_token("google", "g-owner", email="owner@example.com", verified=True, aud="google-web-client")
    r = await client.post("/api/v1/auth/social-login", json={"provider": "google", "token": verified})
    assert r.json()["user"]["id"] == str(existing.id)


async def test_google_unconfigured_is_rejected(client: AsyncClient, monkeypatch) -> None:
    from shared.config import get_settings

    monkeypatch.setattr(get_settings().identity, "GOOGLE_CLIENT_IDS", [])
    monkeypatch.setattr(get_settings().identity, "GOOGLE_CLIENT_ID", "")
    r = await client.post("/api/v1/auth/social-login", json={"provider": "google", "token": "x" * 20})
    assert r.status_code == 401


# ── Account deletion ──────────────────────────────────────────────────────────

async def test_delete_account_removes_personal_data_and_sessions(client: AsyncClient, db_session) -> None:
    user = await make_user(db_session, "bye@example.com", phone="+14155550199", assignments=[("viewer", "US")])
    db_session.add(Address(user_id=user.id, label="Home", street="1 Main St", city="Boise",
                           state="ID", postal_code="83702", country="US"))
    await db_session.flush()
    tokens = await login(client, "bye@example.com")

    r = await client.delete("/api/v1/users/me", headers=bearer(tokens))
    assert r.status_code == 200, r.text

    await db_session.refresh(user)
    assert (user.email, user.phone, user.full_name, user.is_active) == (None, None, "Deleted user", False)
    assert (await db_session.execute(select(Address).where(Address.user_id == user.id))).first() is None
    assert (await db_session.execute(select(AdminRoleAssignment).where(AdminRoleAssignment.user_id == user.id))).first() is None
    assert (await client.get("/api/v1/users/me", headers=bearer(tokens))).status_code == 401
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})).status_code == 401
    r = await client.post("/api/v1/auth/login", json={"email": "bye@example.com", "password": PASSWORD})
    assert r.status_code == 401


# ── Admin roles API ───────────────────────────────────────────────────────────

@pytest.fixture
async def admins(db_session) -> dict[str, User]:
    tag = uuid.uuid4().hex[:6]
    spec = {
        "super": ("US", [("super_admin", "*")]),
        "cm_in": ("IN", [("country_manager", "IN")]),
        "ops_hyd": ("IN", [("city_ops", "IN-TG-HYD")]),
        "support_hyd": ("IN", [("support_agent", "IN-TG-HYD")]),
        "finance_in": ("IN", [("finance", "IN")]),
        "viewer_us": ("US", [("viewer", "US")]),
    }
    out = {}
    for name, (country, roles) in spec.items():
        out[name] = await make_user(db_session, f"{name}.{tag}@example.com", country=country, role="admin", assignments=roles)
    out["cust_in"] = await make_user(db_session, f"cust_in.{tag}@example.com", country="IN")
    out["cust_us"] = await make_user(db_session, f"cust_us.{tag}@example.com", country="US")
    return out


async def as_(client: AsyncClient, user: User) -> dict:
    return bearer(await login(client, user.email))


async def test_admin_token_carries_roles_and_me_lists_permissions(client: AsyncClient, admins) -> None:
    t = await login(client, admins["ops_hyd"].email)
    assert t["admin_roles"] == ["city_ops@IN-TG-HYD"]
    assert decode_access_token(t["access_token"])["adm"] == ["city_ops@IN-TG-HYD"]
    me = (await client.get("/api/v1/admin/me", headers=bearer(t))).json()
    assert me["permissions"]["orders.edit"] == ["IN-TG-HYD"]
    assert "rules.approve" not in me["permissions"]


async def test_customers_are_not_admins(client: AsyncClient, admins) -> None:
    h = await as_(client, admins["cust_in"])
    assert (await client.get("/api/v1/admin/me", headers=h)).status_code == 403
    assert (await client.get(f"/api/v1/users/{admins['cust_us'].id}", headers=h)).status_code == 403


@pytest.mark.parametrize(("granter", "role", "scope", "status"), [
    ("super", "country_manager", "US", 201),
    ("cm_in", "city_ops", "IN-TG-HYD", 201),
    ("cm_in", "support_agent", "IN-KA-BLR", 201),
    ("cm_in", "city_ops", "US-ID-BOI", 403),
    ("cm_in", "country_manager", "IN", 403),
    ("ops_hyd", "support_agent", "IN-TG-HYD", 403),
    ("finance_in", "viewer", "IN", 403),
    ("viewer_us", "viewer", "US", 403),
    ("super", "super_admin", "IN", 422),
    ("super", "city_ops", "hyderabad", 422),
])
async def test_grant_rules(client: AsyncClient, admins, granter, role, scope, status) -> None:
    h = await as_(client, admins[granter])
    r = await client.post("/api/v1/admin/role-assignments", headers=h,
                          json={"email": admins["cust_in"].email, "role": role, "scope": scope})
    assert r.status_code == status, r.text


async def test_granted_role_works_and_revoke_takes_effect_at_once(client: AsyncClient, admins) -> None:
    cm = await as_(client, admins["cm_in"])
    r = await client.post("/api/v1/admin/role-assignments", headers=cm,
                          json={"user_id": str(admins["cust_in"].id), "role": "support_agent", "scope": "IN-TG-HYD"})
    assert r.status_code == 201
    assignment_id = r.json()["id"]

    agent = await as_(client, admins["cust_in"])
    assert (await client.get(f"/api/v1/users/{admins['cust_in'].id}", headers=agent)).status_code == 200

    assert (await client.delete(f"/api/v1/admin/role-assignments/{assignment_id}", headers=cm)).status_code == 204
    # Same access token, role gone: refused immediately.
    assert (await client.get(f"/api/v1/users/{admins['cust_in'].id}", headers=agent)).status_code == 403


@pytest.mark.parametrize(("admin", "target", "status"), [
    ("super", "cust_us", 200),
    ("cm_in", "cust_in", 200),
    ("cm_in", "cust_us", 403),
    ("ops_hyd", "cust_in", 200),
    ("ops_hyd", "cust_us", 403),
    ("support_hyd", "cust_in", 200),
    ("finance_in", "cust_in", 403),     # finance has no customers.view
    ("viewer_us", "cust_us", 200),
    ("viewer_us", "cust_in", 403),
])
async def test_view_customer_by_scope(client: AsyncClient, admins, admin, target, status) -> None:
    h = await as_(client, admins[admin])
    assert (await client.get(f"/api/v1/users/{admins[target].id}", headers=h)).status_code == status


@pytest.mark.parametrize(("admin", "status"), [
    ("support_hyd", 200), ("cm_in", 200), ("ops_hyd", 403), ("viewer_us", 403), ("finance_in", 403),
])
async def test_erase_customer_needs_customers_edit(client: AsyncClient, admins, admin, status) -> None:
    h = await as_(client, admins[admin])
    r = await client.delete(f"/api/v1/users/{admins['cust_in'].id}/anonymize", headers=h)
    assert r.status_code == status


async def test_role_assignment_list_is_scoped(client: AsyncClient, admins) -> None:
    cm = await as_(client, admins["cm_in"])
    scopes = {a["scope"] for a in (await client.get("/api/v1/admin/role-assignments", headers=cm)).json()}
    assert scopes and all(s == "IN" or s.startswith("IN-") for s in scopes)
    sup = await as_(client, admins["super"])
    all_scopes = {a["scope"] for a in (await client.get("/api/v1/admin/role-assignments", headers=sup)).json()}
    assert {"*", "US", "IN-TG-HYD"} <= all_scopes
    viewer = await as_(client, admins["viewer_us"])
    assert (await client.get("/api/v1/admin/role-assignments", headers=viewer)).status_code == 403
