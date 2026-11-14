"""Rate limits key on the client, not the platform proxy in front of it (Railway QA)."""
from starlette.requests import Request

from shared.client_ip import client_ip
from shared.config import get_settings


def request(headers: dict[str, str], peer: str = "100.64.0.16") -> Request:
    return Request({"type": "http", "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
                    "client": (peer, 40000)})


def test_without_a_header_setting_the_socket_peer_is_the_client(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(get_settings(), "CLIENT_IP_HEADER", "")
    assert client_ip(request({"X-Real-IP": "24.117.189.227"})) == "100.64.0.16"  # a header alone isn't trusted


def test_behind_railway_the_edge_header_is_the_client(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(get_settings(), "CLIENT_IP_HEADER", "X-Real-IP")
    assert client_ip(request({"X-Real-IP": "24.117.189.227"})) == "24.117.189.227"
    assert client_ip(request({"X-Real-IP": " 24.117.189.227 , 10.0.0.1"})) == "24.117.189.227"
    assert client_ip(request({})) == "100.64.0.16"  # a private caller (no edge): its own address
