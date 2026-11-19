"""R19: the first super admin of a new environment (core_api/modules/identity/first_admin.py)."""
import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.first_admin import FirstAdminError, create_first_admin, super_admin_exists
from core_api.modules.identity.models.admin_role import AdminRoleAssignment
from core_api.modules.identity.models.user import User


async def test_creates_a_super_admin_without_a_password(db_session: AsyncSession) -> None:
    assert not await super_admin_exists(db_session)
    user = await create_first_admin(db_session, "  Owner@Example.org ", " Pat   Owner ", "us")
    assert (user.email, user.full_name, user.role, user.country) == ("owner@example.org", "Pat Owner", "super_admin", "US")
    assert user.hashed_password is None and user.totp_secret is None and user.is_active
    roles = (await db_session.execute(select(AdminRoleAssignment).where(AdminRoleAssignment.user_id == user.id))).scalars().all()
    assert [(r.role, r.scope) for r in roles] == [("super_admin", "*")]
    assert await super_admin_exists(db_session)


async def test_refused_once_any_super_admin_exists(db_session: AsyncSession) -> None:
    await create_first_admin(db_session, "first@example.org", "First Admin")
    with pytest.raises(FirstAdminError, match="already exists"):
        await create_first_admin(db_session, "second@example.org", "Second Admin")


async def test_refused_when_a_super_admin_role_is_assigned(db_session: AsyncSession) -> None:
    """A super admin by role assignment only (users.role not super_admin) counts too."""
    u = User(email="someone@example.org", full_name="Someone", role="admin", country="US")
    db_session.add(u)
    await db_session.flush()
    db_session.add(AdminRoleAssignment(user_id=u.id, role="super_admin", scope="*"))
    await db_session.flush()
    with pytest.raises(FirstAdminError, match="already exists"):
        await create_first_admin(db_session, "owner@example.org", "Owner")


@pytest.mark.parametrize(("email", "name", "country", "says"), [
    ("not-an-email", "Owner", "US", "valid email"),
    ("owner@example.org", "  ", "US", "full name"),
    ("owner@example.org", "Owner", "FR", "country"),
])
async def test_refuses_bad_input(db_session: AsyncSession, email, name, country, says) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(FirstAdminError, match=says):
        await create_first_admin(db_session, email, name, country)


async def test_refuses_an_existing_account(db_session: AsyncSession) -> None:
    db_session.add(User(email="taken@example.org", full_name="Customer", role="customer", country="US"))
    await db_session.flush()
    with pytest.raises(FirstAdminError, match="account with this email"):
        await create_first_admin(db_session, "Taken@example.org", "Owner")


async def test_first_sign_in_sets_the_password_then_enrols_the_authenticator(
        client: AsyncClient, db_session: AsyncSession, outbox) -> None:  # type: ignore[no-untyped-def]
    """The existing flows: forgot password -> reset link by email -> password -> the second step is
    an enrolment (no tokens until an authenticator is confirmed)."""
    user = await create_first_admin(db_session, "owner@example.org", "Pat Owner")
    await db_session.commit()
    try:
        await _first_sign_in(client, outbox)
    finally:  # committed (the API commits): remove it so other tests start with no super admin
        await db_session.execute(delete(AdminRoleAssignment).where(AdminRoleAssignment.user_id == user.id))
        await db_session.execute(delete(User).where(User.id == user.id))
        await db_session.commit()


async def _first_sign_in(client: AsyncClient, outbox) -> None:  # type: ignore[no-untyped-def]
    assert (await client.post("/api/v1/auth/password/forgot", json={"email": "owner@example.org"})).status_code == 202
    from core_api.modules.identity.service import background

    await background.drain()
    link = next(m["body"] for m in outbox if m["to"] == "owner@example.org")
    token = link.split("token=")[1].split('"')[0].split("&")[0]
    r = await client.post("/api/v1/auth/password/reset", json={"token": token, "new_password": "A-long-new-pass-2026"})
    assert r.status_code in (200, 204), r.text
    r = await client.post("/api/v1/auth/login", json={"email": "owner@example.org", "password": "A-long-new-pass-2026"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "access_token" not in body
    assert body["mfa_required"] and body["mfa_token"] and body["enrolment_required"] is True
