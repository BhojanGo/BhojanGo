"""
Pytest configuration for backend API tests.
"""
import pytest
import httpx


# Configure pytest-asyncio to use function scope for all async fixtures
# This avoids the "Event loop is closed" issue with session-scoped async fixtures
pytest_plugins = ["pytest_asyncio"]


@pytest.fixture
async def client():
    """Function-scoped async HTTP client - avoids event loop closure issues."""
    async with httpx.AsyncClient(timeout=30.0) as c:
        yield c


@pytest.fixture
async def auth_tokens(client: httpx.AsyncClient) -> dict[str, str]:
    """
    Logs in each role and returns a dict mapping role name to access token.
    Uses function scope to avoid asyncio event loop issues.
    """
    base_url = "http://localhost:8001/api/v1/auth/login"

    credentials = {
        "customer": ("customer1@test.com", "Test1234!"),
        "owner": ("owner1@test.com", "Test1234!"),
        "driver": ("driver1@test.com", "Test1234!"),
        "admin": ("admin@bhojango.com", "Admin1234!"),
        "super_admin": ("rr_admin@bhojango.com", "Arr@Admin1"),
    }

    tokens: dict[str, str] = {}

    for role, (email, password) in credentials.items():
        payload = {"email": email, "password": password}
        try:
            response = await client.post(base_url, json=payload)
            if response.status_code == 200:
                tokens[role] = response.json()["access_token"]
        except Exception:
            # If login fails, continue with other roles
            pass

    return tokens


@pytest.fixture(scope="session")
def service_urls() -> dict[str, int]:
    """Mapping of service names to their localhost ports."""
    return {
        "user": 8001,
        "restaurant": 8002,
        "order": 8003,
        "delivery": 8004,
        "payment": 8005,
        "notification": 8006,
        "batch": 8007,
    }