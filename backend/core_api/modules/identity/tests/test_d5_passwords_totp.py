"""Round 8 D5: the building blocks. Argon2id hashing and rehash of bcrypt, the
new-password rules with the breached-password check (a fake; no network),
RFC 6238 codes, encrypted secrets, recovery codes and the fixed email code."""
import base64
import hashlib

import bcrypt
import httpx
import pytest

from core_api.modules.identity.service import email_codes, passwords, totp
from shared.config import get_settings

# ── hashing ──────────────────────────────────────────────────────────────────


def test_hashes_are_argon2id_and_salted() -> None:
    a, b = passwords.hash_password("Correct-horse-1"), passwords.hash_password("Correct-horse-1")
    assert a.startswith("$argon2id$") and a != b
    assert "m=19456,t=2,p=1" in a
    assert passwords.verify_password("Correct-horse-1", a)
    assert not passwords.verify_password("Correct-horse-2", a)
    assert not passwords.needs_rehash(a)


def test_legacy_bcrypt_hashes_verify_and_need_a_rehash() -> None:
    legacy = bcrypt.hashpw(b"BhojanGo123", bcrypt.gensalt(rounds=4)).decode()
    assert passwords.verify_password("BhojanGo123", legacy)
    assert not passwords.verify_password("BhojanGo124", legacy)
    assert passwords.needs_rehash(legacy)


@pytest.mark.parametrize("stored", [None, "", "not-a-hash", "$argon2id$garbage", "$2b$garbage"])
def test_bad_or_missing_hashes_never_match_or_raise(stored) -> None:
    assert passwords.verify_password("anything-at-all", stored) is False


def test_unicode_forms_hash_the_same() -> None:
    composed, decomposed = "Café-password-1", "Café-password-1"
    assert passwords.verify_password(decomposed, passwords.hash_password(composed))


# ── new-password rules ──────────────────────────────────────────────────────


async def test_minimum_length_is_ten_characters() -> None:
    with pytest.raises(passwords.PasswordRejected) as e:
        await passwords.validate_new_password("nine-char", email="a@example.com")
    assert e.value.code == "PASSWORD_TOO_SHORT"
    await passwords.validate_new_password("ten-chars!", email="a@example.com")
    await passwords.validate_new_password("नमस्ते दुनिया जी", email=None)  # characters, not bytes


async def test_too_long_and_like_the_email_are_rejected() -> None:
    with pytest.raises(passwords.PasswordRejected) as e:
        await passwords.validate_new_password("x" * 129, email=None)
    assert e.value.code == "PASSWORD_TOO_LONG"
    for pw, email in (("asha.rao@example.com", "asha.rao@example.com"), ("ASHA.RAO@EXAMPLE.COM!", "asha.rao@example.com"),
                      ("ashwini.rao", "ashwini.rao@example.com")):
        with pytest.raises(passwords.PasswordRejected) as e:
            await passwords.validate_new_password(pw, email=email)
        assert e.value.code == "PASSWORD_LIKE_EMAIL"


async def test_breached_passwords_are_rejected(breaches) -> None:
    with pytest.raises(passwords.PasswordRejected) as e:
        await passwords.validate_new_password("password1234", email="a@example.com")
    assert e.value.code == "PASSWORD_BREACHED"
    assert breaches.asked == ["password1234"]


async def test_an_unreachable_breach_service_never_blocks(breaches) -> None:
    breaches.down = True
    await passwords.validate_new_password("password1234", email="a@example.com")


def _mock_client(handler):  # type: ignore[no-untyped-def]
    real = httpx.AsyncClient

    def factory(*args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs.pop("timeout", None)
        return real(transport=httpx.MockTransport(handler), timeout=1)

    return factory


async def test_pwned_passwords_sends_only_five_hex_characters(monkeypatch) -> None:
    seen: list[httpx.Request] = []
    digest = hashlib.sha1(b"hunter2-but-longer").hexdigest().upper()

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text=f"0000000000000000000000000000000000A:0\r\n{digest[5:]}:42\r\n")

    monkeypatch.setattr(passwords.httpx, "AsyncClient", _mock_client(handler))
    assert await passwords.PwnedPasswords().times_seen("hunter2-but-longer") == 42
    assert await passwords.PwnedPasswords().times_seen("something-else-entirely") == 0
    url = str(seen[0].url)
    assert url == f"https://api.pwnedpasswords.com/range/{digest[:5]}"
    assert digest[5:] not in url and "hunter2" not in url
    assert seen[0].headers["Add-Padding"] == "true"


async def test_pwned_passwords_down_answers_none(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow", request=request)

    monkeypatch.setattr(passwords.httpx, "AsyncClient", _mock_client(handler))
    assert await passwords.PwnedPasswords().times_seen("whatever-password") is None


# ── TOTP (RFC 6238) ─────────────────────────────────────────────────────────

RFC_SECRET = base64.b32encode(b"12345678901234567890").decode()  # the RFC's SHA-1 test key


@pytest.mark.parametrize(("t", "code"), [(59, "287082"), (1111111109, "081804"), (1234567890, "005924"),
                                         (2000000000, "279037")])
def test_rfc_6238_test_vectors(t: int, code: str) -> None:
    assert totp.code_at(RFC_SECRET, t // 30) == code


def test_codes_match_within_one_step_and_never_twice() -> None:
    now = 1_800_000_000.0
    step = totp.current_step(now)
    for drift in (-1, 0, 1):
        assert totp.matching_step(RFC_SECRET, totp.code_at(RFC_SECRET, step + drift), now=now) == step + drift
    assert totp.matching_step(RFC_SECRET, totp.code_at(RFC_SECRET, step + 2), now=now) is None
    assert totp.matching_step(RFC_SECRET, totp.code_at(RFC_SECRET, step - 2), now=now) is None
    # Replay: a step at or before the last accepted one is refused.
    assert totp.matching_step(RFC_SECRET, totp.code_at(RFC_SECRET, step), last_step=step, now=now) is None
    assert totp.matching_step(RFC_SECRET, totp.code_at(RFC_SECRET, step + 1), last_step=step, now=now) == step + 1
    for bad in ("", "12345", "1234567", "abcdef"):
        assert totp.matching_step(RFC_SECRET, bad, now=now) is None


def test_new_secrets_are_160_random_bits_and_the_uri_names_bhojango() -> None:
    a, b = totp.generate_secret(), totp.generate_secret()
    assert a != b and len(base64.b32decode(a)) == 20
    uri = totp.otpauth_uri(a, "ops@example.com")
    assert uri.startswith("otpauth://totp/BhojanGo%3Aops%40example.com?") and f"secret={a}" in uri
    assert totp.qr_svg_data_uri(uri).startswith("data:image/svg+xml;base64,")


def test_secrets_are_stored_encrypted() -> None:
    secret = totp.generate_secret()
    sealed = totp.encrypt_secret(secret)
    assert secret not in sealed and totp.decrypt_secret(sealed) == secret
    assert totp.decrypt_secret("not-a-fernet-token") is None


def test_production_refuses_to_store_secrets_without_a_key(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    monkeypatch.setattr(get_settings().identity, "IDENTITY_DATA_KEYS", [])
    with pytest.raises(RuntimeError):
        totp.encrypt_secret(totp.generate_secret())


def test_recovery_codes_are_ten_distinct_and_hashed() -> None:
    codes = totp.generate_recovery_codes()
    assert len(codes) == 10 == len(set(codes))
    assert all(len(c) == 11 and c[5] == "-" for c in codes)
    h = totp.hash_recovery_code(codes[0])
    assert codes[0] not in h and len(h) == 64
    assert totp.hash_recovery_code(codes[0].lower().replace("-", " ")) == h  # forgiving about case and dashes


# ── the fixed email code (seed and tests) ───────────────────────────────────

def test_fixed_email_code_only_for_example_com_outside_production(monkeypatch) -> None:
    assert email_codes.fixed_code_for("qa@example.com") == "123456"
    assert email_codes.fixed_code_for("someone@gmail.com") is None
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    assert email_codes.fixed_code_for("qa@example.com") is None


def test_other_services_read_admin_rights_only_from_a_second_step_token() -> None:
    """realtime, worker and core_api's own claim-based checks (shared/auth.CurrentUser)."""
    from shared.auth import CurrentUser

    claims = {"sub": "6f1d3c52-6b0e-4a63-9a0d-5b7f6a2b8a11", "role": "admin", "country": "IN", "adm": ["super_admin@*"]}
    assert CurrentUser.from_claims(claims).admin == []
    assert CurrentUser.from_claims({**claims, "mfa": True}).admin == ["super_admin@*"]
