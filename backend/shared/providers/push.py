"""Push notifications: log (local) or live, where each device goes to the
service that issued its token: Expo (Expo apps), FCM (Android, web) or APNs
(native iOS).

Every provider reports which tokens are dead (app uninstalled, token rotated)
so the worker can forget them.
"""
import time
from dataclasses import dataclass, field
from typing import Protocol

import httpx
import structlog

from shared.config import get_settings
from shared.providers import ProviderConfigError, refuse_in_production

logger = structlog.get_logger(__name__)

PROVIDERS = ("expo", "fcm", "apns")


@dataclass(frozen=True)
class Device:
    token: str
    provider: str = "fcm"  # expo | fcm | apns


@dataclass(frozen=True)
class PushMessage:
    title: str
    body: str
    data: dict[str, str] = field(default_factory=dict)


@dataclass
class PushResult:
    sent: int = 0
    invalid: list[str] = field(default_factory=list)  # tokens to delete

    def add(self, other: "PushResult") -> "PushResult":
        return PushResult(self.sent + other.sent, self.invalid + other.invalid)


def provider_for_token(token: str, platform: str = "") -> str:
    """Which service a token belongs to, when the app didn't say."""
    if token.startswith(("ExponentPushToken[", "ExpoPushToken[")):
        return "expo"
    if platform == "ios" and len(token) == 64 and all(c in "0123456789abcdefABCDEF" for c in token):
        return "apns"
    return "fcm"


class PushProvider(Protocol):
    name: str

    async def send(self, devices: list[Device], message: PushMessage) -> PushResult: ...


class LogPush:
    """Prints the message to the worker log (local development and tests)."""

    name = "log"

    async def send(self, devices: list[Device], message: PushMessage) -> PushResult:
        logger.info("push_local", devices=len(devices), title=message.title, body=message.body, data=message.data)
        print(f"[PUSH to {len(devices)} device(s)] {message.title}: {message.body}", flush=True)
        return PushResult(sent=len(devices))


class ExpoPush:
    """Expo push service (apps built with Expo: the customer, rider and partner apps)."""

    name = "expo"
    URL = "https://exp.host/--/api/v2/push/send"
    DEAD = {"DeviceNotRegistered"}

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client

    async def send(self, devices: list[Device], message: PushMessage) -> PushResult:
        token = get_settings().providers.EXPO_ACCESS_TOKEN
        headers = {"accept": "application/json", "content-type": "application/json",
                   **({"authorization": f"Bearer {token}"} if token else {})}
        result = PushResult()
        for i in range(0, len(devices), 100):  # Expo takes 100 messages per request
            batch = devices[i:i + 100]
            body = [{"to": d.token, "title": message.title, "body": message.body, "data": message.data,
                     "sound": "default", "priority": "high", "channelId": "orders"} for d in batch]
            try:
                async with (self.client or httpx.AsyncClient(timeout=10)) as client:
                    r = await client.post(self.URL, json=body, headers=headers)
                r.raise_for_status()
                tickets = r.json().get("data", [])
            except (httpx.HTTPError, ValueError) as e:
                logger.error("push_failed", provider="expo", devices=len(batch), error=str(e))
                continue
            for d, t in zip(batch, tickets):
                if t.get("status") == "ok":
                    result.sent += 1
                elif (t.get("details") or {}).get("error") in self.DEAD:
                    result.invalid.append(d.token)
                else:
                    logger.warning("push_rejected", provider="expo", error=t.get("message"))
        return result


class FcmPush:
    """Firebase Cloud Messaging (Android and web)."""

    name = "fcm"

    async def send(self, devices: list[Device], message: PushMessage) -> PushResult:
        from app.services.fcm import get_firebase_app  # worker only

        app = get_firebase_app()
        if app is None:
            logger.info("fcm_not_configured", devices=len(devices), title=message.title)
            return PushResult(sent=len(devices))
        from firebase_admin import messaging

        tokens = [d.token for d in devices]
        resp = messaging.send_each_for_multicast(messaging.MulticastMessage(
            notification=messaging.Notification(title=message.title, body=message.body),
            data=message.data, tokens=tokens,
            android=messaging.AndroidConfig(priority="high"),
        ), app=app)
        invalid = [t for t, r in zip(tokens, resp.responses)
                   if not r.success and isinstance(r.exception, (messaging.UnregisteredError, messaging.SenderIdMismatchError))]
        return PushResult(sent=resp.success_count, invalid=invalid)


class ApnsPush:
    """Apple Push Notification service over HTTP/2 with a token (.p8) key."""

    name = "apns"
    DEAD = {"BadDeviceToken", "Unregistered", "DeviceTokenNotForTopic"}
    _jwt: tuple[float, str] | None = None

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client

    def _token(self) -> str:
        import jwt

        p = get_settings().providers
        now = time.time()
        if ApnsPush._jwt and now - ApnsPush._jwt[0] < 45 * 60:  # Apple wants a new one at most hourly
            return ApnsPush._jwt[1]
        signed = jwt.encode({"iss": p.APNS_TEAM_ID, "iat": int(now)}, p.APNS_PRIVATE_KEY.replace("\\n", "\n"),
                            algorithm="ES256", headers={"kid": p.APNS_KEY_ID})
        ApnsPush._jwt = (now, signed)
        return signed

    async def send(self, devices: list[Device], message: PushMessage) -> PushResult:
        p = get_settings().providers
        if not (p.APNS_KEY_ID and p.APNS_TEAM_ID and p.APNS_PRIVATE_KEY):
            raise ProviderConfigError("APNs needs APNS_KEY_ID, APNS_TEAM_ID and APNS_PRIVATE_KEY")
        host = "https://api.sandbox.push.apple.com" if p.APNS_SANDBOX else "https://api.push.apple.com"
        headers = {"authorization": f"bearer {self._token()}", "apns-topic": p.APNS_BUNDLE_ID,
                   "apns-push-type": "alert", "apns-priority": "10"}
        payload = {"aps": {"alert": {"title": message.title, "body": message.body}, "sound": "default"}, **message.data}
        result = PushResult()
        async with (self.client or httpx.AsyncClient(http2=True, timeout=10)) as client:
            for d in devices:
                try:
                    r = await client.post(f"{host}/3/device/{d.token}", json=payload, headers=headers)
                except httpx.HTTPError as e:
                    logger.error("push_failed", provider="apns", error=str(e))
                    continue
                if r.status_code == 200:
                    result.sent += 1
                    continue
                reason = r.json().get("reason", "") if r.content else ""
                if r.status_code == 410 or reason in self.DEAD:
                    result.invalid.append(d.token)
                else:
                    logger.warning("push_rejected", provider="apns", status=r.status_code, reason=reason)
        return result


class LivePush:
    """Sends each device through the service that issued its token."""

    name = "live"

    def __init__(self, providers: dict[str, PushProvider] | None = None) -> None:
        self.providers = providers or {"expo": ExpoPush(), "fcm": FcmPush(), "apns": ApnsPush()}

    async def send(self, devices: list[Device], message: PushMessage) -> PushResult:
        result = PushResult()
        for name, provider in self.providers.items():
            mine = [d for d in devices if d.provider == name]
            if mine:
                try:
                    result = result.add(await provider.send(mine, message))
                except Exception as e:  # noqa: BLE001 - one service down shouldn't stop the others
                    logger.error("push_failed", provider=name, devices=len(mine), error=str(e))
        return result


def get_push_provider() -> PushProvider:
    name = get_settings().providers.PUSH_PROVIDER
    if name == "log":
        refuse_in_production("Push", name)
        return LogPush()
    if name in ("live", "fcm"):  # "fcm" was the old name for live push
        return LivePush()
    raise ProviderConfigError(f"Unknown PUSH_PROVIDER '{name}' (log | live)")
