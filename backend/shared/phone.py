"""R38: phone numbers by country (the ``phonenumbers`` port of libphonenumber; the clients use
libphonenumber-js, packages/ui/phone.js, with the same rules).

* ``normalize``: what was typed, in the country's way or with a "+" and any country's code, as
  E.164 (+12085550123), or ``None`` when it isn't a real number. Numbers are stored E.164 only.
  An international number is allowed anywhere (a US number for an India address is fine); only
  a number that isn't valid at all is refused.
* ``format_phone``: how a stored number is shown: "+1 (208) 555-0123" (the +1 countries),
  "+91 98765 43210" (others: the international format).
"""
import phonenumbers


def normalize(raw: str | None, country: str | None = None) -> str | None:
    text = (raw or "").strip()
    if not any(ch.isdigit() for ch in text):
        return None
    region = country.upper() if country and len(country) == 2 else None
    if not text.startswith("+") and region is None:
        text = "+" + text.lstrip("0")  # digits without a country: as an international number
    try:
        p = phonenumbers.parse(text, region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(p):
        return None
    return phonenumbers.format_number(p, phonenumbers.PhoneNumberFormat.E164)


def format_phone(e164: str | None) -> str:
    if not e164:
        return ""
    try:
        p = phonenumbers.parse(e164, None)
    except phonenumbers.NumberParseException:
        return e164
    if p.country_code == 1:
        return "+1 " + phonenumbers.format_number(p, phonenumbers.PhoneNumberFormat.NATIONAL)
    return phonenumbers.format_number(p, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
