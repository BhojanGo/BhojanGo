"""R22: core_api/routing_speed.py's prefix check never changes which route answers.

For every route of the app (and some paths no route has), each top-level route's match
(full, partial or none) is the same with FastAPI's own matching and with the check.
"""
import re
import uuid

from starlette.routing import Match

from core_api import routing_speed


def _paths(app) -> list[str]:  # type: ignore[no-untyped-def]
    out = set()
    for r in app.routes:
        for ctx in getattr(r, "effective_route_contexts", lambda: [])():
            p = getattr(ctx, "path", "") or getattr(getattr(ctx, "starlette_route", None), "path", "")
            if p:
                out.add(p)
        if getattr(r, "path", None):
            out.add(r.path)
    concrete = set()
    for p in out:
        concrete.add(re.sub(r"\{[^}:]+:path\}", "a/b", re.sub(r"\{[^}]+\}", str(uuid.uuid4()), p)))
        concrete.add(re.sub(r"\{[^}]+\}", "x", p))
    concrete |= {"/", "/api", "/api/v1", "/api/v1/", "/api/v1/nope", "/api/v1/restaurants/", "/api/v1/restaurantsx",
                 "/health", "/health/", "/metrics", "/docs", "/openapi.json", "/.well-known/jwks.json"}
    return sorted(concrete)


def _matches(app, path: str, method: str) -> list[Match]:  # type: ignore[no-untyped-def]
    out = []
    for r in app.router.routes:
        scope = {"type": "http", "path": path, "root_path": "", "method": method, "headers": [], "query_string": b""}
        out.append(r.matches(scope)[0])
    return out


def test_prefix_check_picks_the_same_route_everywhere() -> None:
    from core_api.main import app

    paths = _paths(app)
    assert len(paths) > 300, len(paths)
    try:
        routing_speed.uninstall_matching()
        before = {(p, m): _matches(app, p, m) for p in paths for m in ("GET", "POST", "PUT", "DELETE")}
    finally:
        routing_speed.install()
    after = {(p, m): _matches(app, p, m) for p in paths for m in ("GET", "POST", "PUT", "DELETE")}
    assert after == before
    # And the check does skip most branches for a menu request.
    branches = [r for r in app.router.routes if type(r).__name__ == "_IncludedRouter"]
    prefixes = [routing_speed.branch_prefix(b) for b in branches]
    assert sum(1 for p in prefixes if p and not "/api/v1/restaurants/x/menu".startswith(p)) > len(branches) // 2


def test_answers_are_unchanged_through_the_app() -> None:
    from fastapi.testclient import TestClient

    from core_api.main import app

    c = TestClient(app)
    assert c.get("/health/live").status_code == 200
    assert c.get("/api/v1/does-not-exist").status_code == 404
    assert c.post("/health/live").status_code == 405  # a partial match still wins over "not found"
