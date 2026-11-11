"""Push notifications: log (local) or FCM."""
from typing import Protocol

import structlog

from shared.config import get_settings
from shared.providers import ProviderConfigError, refuse_in_production

logger = structlog.get_logger(__name__)


class PushProvider(Protocol):
    name: str

    async def send(self, tokens: list[str], title: str, body: str, data: dict[str, str] | None = None) -> int:
        """Returns how many devices accepted the message."""
        ...


class LogPush:
    name = "log"

    async def send(self, tokens: list[str], title: str, body: str, data: dict[str, str] | None = None) -> int:
        logger.info("push_local", devices=len(tokens), title=title, body=body, data=data or {})
        print(f"[PUSH to {len(tokens)} device(s)] {title}: {body}", flush=True)
        return len(tokens)


class FcmPush:
    name = "fcm"

    async def send(self, tokens: list[str], title: str, body: str, data: dict[str, str] | None = None) -> int:
        from app.services import fcm  # worker only

        result = await fcm.send_multicast(tokens, title, body, data)
        return int(result.get("success_count", 0)) if isinstance(result, dict) else len(tokens)


def get_push_provider() -> PushProvider:
    name = get_settings().providers.PUSH_PROVIDER
    if name == "log":
        refuse_in_production("Push", name)
        return LogPush()
    if name == "fcm":
        return FcmPush()
    raise ProviderConfigError(f"Unknown PUSH_PROVIDER '{name}'")
