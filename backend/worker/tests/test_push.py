"""P15 push: Expo, APNs and FCM behind one interface; dead tokens reported."""
import json

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from shared.config import get_settings
from shared.providers import ProviderConfigError
from shared.providers.push import (
    ApnsPush, Device, ExpoPush, LivePush, LogPush, PushMessage, PushResult, get_push_provider, provider_for_token,
)

MSG = PushMessage("Cooking now", "Spice Route is cooking your order. Arriving around 8:24 PM.", {"order_id": "o1"})


def test_provider_from_token() -> None:
    assert provider_for_token("ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]") == "expo"
    assert provider_for_token("a" * 64, "ios") == "apns"
    assert provider_for_token("a" * 64, "android") == "fcm"
    assert provider_for_token("fcm-token:APA91b" + "x" * 100, "android") == "fcm"


async def test_expo_sends_and_reports_dead_tokens() -> None:
    seen: list = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(json.loads(req.content))
        return httpx.Response(200, json={"data": [
            {"status": "ok", "id": "t1"},
            {"status": "error", "message": "gone", "details": {"error": "DeviceNotRegistered"}},
            {"status": "error", "message": "slow down", "details": {"error": "MessageRateExceeded"}},
        ]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    res = await ExpoPush(client).send([Device("ExponentPushToken[a]", "expo"), Device("ExponentPushToken[b]", "expo"),
                                       Device("ExponentPushToken[c]", "expo")], MSG)
    assert res.sent == 1 and res.invalid == ["ExponentPushToken[b]"]
    assert seen[0][0] == {"to": "ExponentPushToken[a]", "title": MSG.title, "body": MSG.body, "data": {"order_id": "o1"},
                          "sound": "default", "priority": "high", "channelId": "orders"}


@pytest.fixture
def apns_keys(monkeypatch):  # type: ignore[no-untyped-def]
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    p = get_settings().providers
    for k, v in {"APNS_KEY_ID": "KEY123", "APNS_TEAM_ID": "TEAM45", "APNS_PRIVATE_KEY": pem, "APNS_SANDBOX": True}.items():
        monkeypatch.setattr(p, k, v)
    ApnsPush._jwt = None
    return key.public_key()


async def test_apns_request_and_dead_tokens(apns_keys) -> None:  # type: ignore[no-untyped-def]
    import jwt

    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        token = req.url.path.rsplit("/", 1)[1]
        if token == "b" * 64:
            return httpx.Response(410, json={"reason": "Unregistered"})
        if token == "c" * 64:
            return httpx.Response(400, json={"reason": "BadDeviceToken"})
        return httpx.Response(200)

    res = await ApnsPush(httpx.AsyncClient(transport=httpx.MockTransport(handler))).send(
        [Device("a" * 64, "apns"), Device("b" * 64, "apns"), Device("c" * 64, "apns")], MSG)
    assert res.sent == 1 and res.invalid == ["b" * 64, "c" * 64]
    req = seen[0]
    assert str(req.url).startswith("https://api.sandbox.push.apple.com/3/device/")
    assert req.headers["apns-topic"] == "com.bhojango.app" and req.headers["apns-push-type"] == "alert"
    claims = jwt.decode(req.headers["authorization"].split()[1], apns_keys, algorithms=["ES256"])
    assert claims["iss"] == "TEAM45" and jwt.get_unverified_header(req.headers["authorization"].split()[1])["kid"] == "KEY123"
    assert json.loads(req.content)["aps"]["alert"] == {"title": MSG.title, "body": MSG.body}


async def test_apns_needs_keys(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(get_settings().providers, "APNS_KEY_ID", "")
    with pytest.raises(ProviderConfigError):
        await ApnsPush().send([Device("a" * 64, "apns")], MSG)


class Fake:
    def __init__(self, name: str, fail: bool = False) -> None:
        self.name, self.fail, self.got = name, fail, []

    async def send(self, devices, message):  # type: ignore[no-untyped-def]
        if self.fail:
            raise RuntimeError("service down")
        self.got.extend(d.token for d in devices)
        return PushResult(sent=len(devices))


async def test_live_routes_each_device_to_its_service() -> None:
    expo, fcm, apns = Fake("expo"), Fake("fcm", fail=True), Fake("apns")
    res = await LivePush({"expo": expo, "fcm": fcm, "apns": apns}).send(
        [Device("e1", "expo"), Device("f1", "fcm"), Device("a1", "apns"), Device("e2", "expo")], MSG)
    assert expo.got == ["e1", "e2"] and apns.got == ["a1"]
    assert res.sent == 3  # FCM being down doesn't stop Expo and APNs


def test_provider_selection(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    assert isinstance(get_push_provider(), LogPush)
    monkeypatch.setattr(get_settings().providers, "PUSH_PROVIDER", "live")
    assert isinstance(get_push_provider(), LivePush)
