"""Contract tests between our services (P22): realtime calls core_api's internal
endpoints and reads fields from what they return. If core_api renames a path or
a field, these fail here instead of in a rider's app at dispatch time."""
import re
from pathlib import Path

from fastapi.routing import APIRoute

from shared.contracts import DispatchInfo

BACKEND = Path(__file__).resolve().parents[4]
REALTIME = BACKEND / "realtime" / "app"


def _all_routes():  # type: ignore[no-untyped-def]
    """(methods, path, response_model) for every route, including ones left out of
    the OpenAPI document and ones inside included routers (FastAPI wraps those)."""
    from core_api.main import app

    for r in app.routes:
        if isinstance(r, APIRoute):
            yield r.methods, r.path, r.response_model
        elif type(r).__name__ == "_IncludedRouter":
            for c in r.effective_route_contexts():
                yield c.methods or set(), c.path, c.response_model


def _core_routes() -> set[tuple[str, str]]:
    return {(m, re.sub(r"\{[^}]+\}", "{}", path)) for methods, path, _ in _all_routes() for m in methods}


def _realtime_calls() -> set[tuple[str, str]]:
    src = (REALTIME / "services" / "core_api.py").read_text(encoding="utf-8")
    calls = {(m, p) for m, p in re.findall(r'_call\("([A-Z]+)",\s*f?"([^"]+)"', src)}
    calls |= {("GET", p) for p in re.findall(r'client\.get\(\s*f?"([^"]+)"', src)}
    return {(m, re.sub(r"\{[^}]+\}", "{}", p)) for m, p in calls}


def test_every_core_path_realtime_calls_exists() -> None:
    calls = _realtime_calls()
    assert len(calls) >= 4, calls  # the parser still finds them
    missing = calls - _core_routes()
    assert not missing, f"realtime calls core_api paths that don't exist: {sorted(missing)}"


def test_every_dispatch_field_realtime_reads_is_in_the_contract() -> None:
    read: set[str] = set()
    for f in REALTIME.rglob("*.py"):
        src = f.read_text(encoding="utf-8")
        read |= set(re.findall(r'\binfo(?:\.get\(|\[)"([a-z_]+)"', src))
        read |= set(re.findall(r'\boffer(?:\.get\(|\[)"([a-z_]+)"', src)) & set(DispatchInfo.model_fields)
    assert {"order_id", "driver_id", "pickup", "dropoff", "status"} <= read  # the scan works
    unknown = read - set(DispatchInfo.model_fields)
    assert not unknown, f"realtime reads fields core_api doesn't promise: {sorted(unknown)}"


def test_internal_endpoints_return_the_contract() -> None:
    internal = [(path, model) for _, path, model in _all_routes() if path.startswith("/api/v1/internal/orders/")]
    assert len(internal) >= 2, internal  # found them (not a vacuous pass)
    for path, model in internal:
        assert model is DispatchInfo, path
