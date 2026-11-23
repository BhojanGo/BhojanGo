"""The countries we operate in come from Markets (the countries table), not
from lists in the code: sign-up, phone sign-in and new kitchens are checked
against it, so launching a third country is a row an admin adds, not a deploy.

    country exists and isn't draft        -> sign up / open a kitchen there
    a kitchen's currency                  == its country's currency
    a phone number for a country          starts with its phone_code
"""
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class CountryInfo:
    code: str
    currency: str
    phone_code: str
    locales: tuple[str, ...]
    status: str

    @property
    def default_locale(self) -> str:
        """English for the country when it has it (en-IN, en-US), else its first language."""
        english = f"en-{self.code}"
        return english if english in self.locales else (self.locales[0] if self.locales else "en-US")


async def lookup(db: AsyncSession, code: str) -> CountryInfo | None:
    from core_api.modules.markets.models import Country

    c = (await db.execute(select(Country).where(Country.code == code.upper()))).scalar_one_or_none()
    if c is None:
        return None
    return CountryInfo(code=c.code, currency=c.currency, phone_code=c.phone_code, locales=tuple(c.locales or ()),
                       status=c.status)


async def open_currencies(db: AsyncSession) -> set[str]:
    """The currencies of every country that isn't a draft."""
    from core_api.modules.markets.models import Country

    return set((await db.execute(select(Country.currency).where(Country.status != "draft"))).scalars())


def _bad(code: str, message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": code, "message": message})


async def require_open(db: AsyncSession, code: str) -> CountryInfo:
    """The country, if it exists and isn't a draft; else 422 COUNTRY_NOT_AVAILABLE."""
    c = await lookup(db, code)
    if c is None or c.status == "draft":
        raise _bad("COUNTRY_NOT_AVAILABLE", f"We don't operate in {code} yet")
    return c


def require_phone_in(country: CountryInfo, phone: str | None) -> None:
    """A phone number for this country starts with its calling code (+91, +1)."""
    if phone is None:
        return
    digits = phone if phone.startswith("+") else f"+{phone}"
    if not digits.startswith(country.phone_code):
        raise _bad("PHONE_COUNTRY_MISMATCH", f"A phone number in {country.code} starts with {country.phone_code}")


def require_currency_of(country: CountryInfo, currency: str) -> None:
    if currency != country.currency:
        raise _bad("CURRENCY_MISMATCH", f"Restaurants in {country.code} charge in {country.currency}")


async def require_known_currency(db: AsyncSession, currency: str) -> None:
    if currency not in await open_currencies(db):
        raise _bad("CURRENCY_NOT_AVAILABLE", f"We don't charge in {currency}")
