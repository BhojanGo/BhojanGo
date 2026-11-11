"""Redis key builders for identity's tokens and OTPs.

The connection itself (get_redis / close_redis) moved to shared.redis.
"""


def refresh_token_key(user_id: str, jti: str) -> str:
    return f"refresh_token:{user_id}:{jti}"


def otp_key(phone: str) -> str:
    return f"otp:{phone}"


def otp_attempts_key(phone: str) -> str:
    return f"otp_attempts:{phone}"


def blacklist_key(jti: str) -> str:
    return f"token_blacklist:{jti}"
