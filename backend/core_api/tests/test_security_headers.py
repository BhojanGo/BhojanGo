"""Security pass: every API response carries the hardening headers ZAP asked for."""
from httpx import ASGITransport, AsyncClient


async def test_api_responses_carry_security_headers() -> None:
    from core_api.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        for path in ("/health/live", "/api/v1/does-not-exist"):
            r = await c.get(path)
            assert r.headers["x-content-type-options"] == "nosniff", path
            assert r.headers["cross-origin-resource-policy"] == "same-site", path
            assert r.headers["x-frame-options"] == "DENY", path
            assert r.headers["referrer-policy"] == "no-referrer", path
