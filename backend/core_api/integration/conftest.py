import pytest


@pytest.fixture(autouse=True)
def _reset_login_rate_limit():
    """Login is limited to 10/minute per IP; the suite signs in more than that."""
    from core_api.modules.identity.api.v1.auth import limiter

    limiter.reset()
    yield
