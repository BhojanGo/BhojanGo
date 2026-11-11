"""Redis key builders for identity's tokens and OTPs.

The connection itself (get_redis / close_redis) moved to shared.redis.
"""


def refresh_family_key(user_id: str, family: str) -> str:
    """Current (only valid) refresh-token jti of one sign-in session."""
    return f"refresh_family:{user_id}:{family}"


def refresh_families_key(user_id: str) -> str:
    """Set of the user's session families, for signing out everywhere."""
    return f"refresh_families:{user_id}"


def otp_key(phone: str) -> str:
    return f"otp:{phone}"


def otp_attempts_key(phone: str) -> str:
    return f"otp_attempts:{phone}"


def blacklist_key(jti: str) -> str:
    return f"token_blacklist:{jti}"
