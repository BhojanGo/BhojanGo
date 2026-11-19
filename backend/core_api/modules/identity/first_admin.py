"""Create the first super admin of a new environment, once (R19; docs/launch/go-live.md step 12).

    cd backend && python -m core_api.modules.identity.first_admin --email <email> --name "<full name>"

Prints nothing secret, because nothing secret is made: the account has no password yet. Then:

1. On the website, "Forgot password" (/signin/forgot) with that email: the reset link arrives by
   email (Amazon SES in production) and is good for 30 minutes, once.
2. Set the password, then sign in to the admin console: as for every admin without an
   authenticator, the first sign-in enrols one (a code to the email, the QR code, then 10
   recovery codes shown once). No admin session exists before that second step.

Refused when any super admin already exists (more admins are granted in the admin console), or
when an account with that email exists. Runs anywhere core_api's settings load (production:
inside the environment, e.g. `railway ssh` into core-api, or over a database tunnel with the
production variables).
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.models.admin_role import AdminRoleAssignment
from core_api.modules.identity.models.user import User

ROLE, SCOPE = "super_admin", "*"
CURRENCY = {"US": "USD", "IN": "INR"}
LOCALE = {"US": "en-US", "IN": "en-IN"}


class FirstAdminError(Exception):
    """Why the first admin can't be created (shown as is)."""


async def super_admin_exists(db: AsyncSession) -> bool:
    users = (await db.execute(select(func.count()).select_from(User).where(User.role == ROLE))).scalar_one()
    roles = (await db.execute(select(func.count()).select_from(AdminRoleAssignment)
                              .where(AdminRoleAssignment.role == ROLE))).scalar_one()
    return bool(users or roles)


async def create_first_admin(db: AsyncSession, email: str, full_name: str, country: str = "US") -> User:
    """The super admin, with no password and no authenticator (both set by the person). Flushed, not committed."""
    try:
        email = validate_email(email.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError as e:
        raise FirstAdminError(f"not a valid email address: {e}") from None
    full_name = " ".join(full_name.split())
    country = country.strip().upper()
    if not full_name:
        raise FirstAdminError("give the person's full name")
    if country not in CURRENCY:
        raise FirstAdminError(f"country must be one of {', '.join(CURRENCY)}")
    if await super_admin_exists(db):
        raise FirstAdminError("a super admin already exists: grant more admins in the admin console (Admins)")
    taken = (await db.execute(select(User.id).where(func.lower(User.email) == email))).first()
    if taken is not None:
        raise FirstAdminError("an account with this email already exists")
    user = User(email=email, full_name=full_name, hashed_password=None, role=ROLE, country=country,
                preferred_currency=CURRENCY[country], preferred_locale=LOCALE[country],
                is_active=True, is_verified=False)
    db.add(user)
    await db.flush()
    db.add(AdminRoleAssignment(user_id=user.id, role=ROLE, scope=SCOPE))
    await db.flush()
    return user


async def _run(email: str, name: str, country: str) -> int:
    from core_api.modules.identity.service import events
    from shared.db import AsyncSessionLocal, engine

    try:
        async with AsyncSessionLocal() as db:
            user = await create_first_admin(db, email, name, country)
            await events.record(db, user.id, "admin.first_admin_created", role=ROLE, scope=SCOPE)
            await db.commit()
    except FirstAdminError as e:
        print(f"first admin: REFUSED: {e}", file=sys.stderr)
        return 3
    finally:
        await engine.dispose()
    print(f"first admin: created super admin {user.email} (no password yet).\n"
          "Next: the website's 'Forgot password' with this email sends the set-password link (30 minutes, once);\n"
          "then sign in to the admin console and enrol the authenticator (save the 10 recovery codes offline).")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Create the first super admin (refused if one exists).")
    ap.add_argument("--email", required=True)
    ap.add_argument("--name", required=True, help="full name")
    ap.add_argument("--country", default="US", help="the admin's own country (US or IN); default US")
    args = ap.parse_args(argv)
    return asyncio.run(_run(args.email, args.name, args.country))


if __name__ == "__main__":
    sys.exit(main())
