"""R27: kitchen tablet heartbeats must be written where core_api reads them. realtime writes the
socket heartbeats, core_api the poll ones and reads them all for every quote, the worker writes the
demo simulator's. realtime's REDIS_URL is another Redis database (/3), so it sets
KITCHEN_LIVE_REDIS_URL to core_api's; this checks every stack the services run on resolves one
place for shared/kitchen_live.py (compose: make dev, CI, e2e; .railway/railway.ts: QA, staging,
production). Before, realtime's socket heartbeats went to db 3 and counted for nothing."""
import re
from pathlib import Path

import pytest
import yaml

from shared import kitchen_live
from shared.config import get_settings

ROOT = Path(__file__).resolve().parents[3]


def heartbeat_url(env: dict) -> str:
    """What shared/kitchen_live.redis_url() resolves for a service with these variables."""
    return env.get("KITCHEN_LIVE_REDIS_URL") or env["REDIS_URL"]


def test_compose_services_share_the_heartbeat_database() -> None:
    services = yaml.safe_load((ROOT / "infra/docker/compose.yaml").read_text(encoding="utf-8"))["services"]
    urls = {name: heartbeat_url(services[name]["environment"]) for name in ("core-api", "realtime", "worker")}
    assert len(set(urls.values())) == 1, urls
    assert urls["core-api"] == services["core-api"]["environment"]["REDIS_URL"], "core_api reads its own REDIS_URL"


def railway_service(src: str, name: str) -> str:
    start = src.index(f'backend("{name}"')
    return src[start:src.index("});", start)]


@pytest.mark.skipif(not (ROOT / ".railway/railway.ts").exists(), reason="no .railway/railway.ts in this checkout")
def test_railway_services_share_the_heartbeat_database() -> None:
    src = (ROOT / ".railway/railway.ts").read_text(encoding="utf-8")

    def db(block: str, var: str) -> str | None:
        m = re.search(rf"\b{var}:\s*redisDb\((\d+)\)", block)
        return m.group(1) if m else None

    dbs = {}
    for name in ("core-api", "realtime", "worker"):
        block = railway_service(src, name)
        dbs[name] = db(block, "KITCHEN_LIVE_REDIS_URL") or db(block, "REDIS_URL")
    assert dbs["core-api"] is not None and len(set(dbs.values())) == 1, dbs


def test_a_service_on_another_database_uses_the_heartbeat_url(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    s = get_settings()
    monkeypatch.setattr(s, "REDIS_URL", "redis://redis:6379/3")
    monkeypatch.setattr(s, "KITCHEN_LIVE_REDIS_URL", "redis://redis:6379/0")
    assert kitchen_live.redis_url() == "redis://redis:6379/0"
    monkeypatch.setattr(s, "KITCHEN_LIVE_REDIS_URL", "")
    assert kitchen_live.redis_url() == "redis://redis:6379/3"
