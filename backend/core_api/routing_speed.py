"""Cheaper route lookups for core_api (R22 performance).

The R21 load test's profile: finding the route took about a fifth of core_api's CPU,
because three things each walked core_api's ~500 routes on every request:

1. FastAPI itself. Every ``include_router`` is a branch (``_IncludedRouter``), and a
   request is tried against every route of every branch before its own, regex by
   regex. Here each branch first checks the static start its routes share (for
   example ``/api/v1/restaurants``): a path that doesn't start with it can't match
   any of them, so the branch answers "no match" at once. Otherwise FastAPI matches as
   before, in the same order, so the same route wins (core_api/tests/test_routing_speed.py
   checks every route of the app, with and without this).
2. SlowAPIMiddleware: removed (core_api/modules/identity/main.py says why).
3. The Prometheus middleware's route name for its labels: remembered per method and
   path (the route table doesn't change after start-up); bounded.

FastAPI is pinned below 0.163 (pyproject.toml); the test fails if its internals move.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import routing as fr
from starlette._utils import get_route_path
from starlette.routing import Match

_prefixes: dict[int, tuple[Any, Any, str]] = {}  # id(branch) -> (branch, routes version, prefix)
_installed = False


def _static(path: str) -> str:
    return path.split("{", 1)[0]


def branch_prefix(branch: Any) -> str:
    """The static start every route of this branch shares ("" = check nothing)."""
    version = branch.original_router._get_routes_version()
    hit = _prefixes.get(id(branch))
    if hit is not None and hit[0] is branch and hit[1] == version:
        return hit[2]
    paths: list[str] = []
    for c in branch.effective_candidates():
        if isinstance(c, fr._IncludedRouter):
            paths.append(branch_prefix(c))
        elif isinstance(c.original_route, fr.APIRoute) and c.path:
            paths.append(_static(c.path))
        elif c.starlette_route is not None and isinstance(getattr(c.starlette_route, "path", None), str) \
                and not isinstance(c.original_route, fr._FrontendRouteGroup):
            paths.append(_static(c.starlette_route.path))
        else:
            paths = []  # something we can't read: never skip this branch
            break
    prefix = os.path.commonprefix(paths) if paths and all(paths) else ""
    _prefixes[id(branch)] = (branch, version, prefix)
    return prefix


_original_matches = fr._IncludedRouter.matches


def _matches(self: Any, scope: Any) -> tuple[Match, Any]:
    prefix = branch_prefix(self)
    if prefix and not get_route_path(scope).startswith(prefix):
        return Match.NONE, {}
    return _original_matches(self, scope)


_route_names: dict[tuple, tuple[str, bool]] = {}


def _prometheus_handler(original: Any) -> Any:
    def _get_handler(self: Any, request: Any) -> tuple[str, bool]:
        scope = request.scope
        key = (id(self), scope.get("root_path", ""), scope["path"], scope.get("method"))
        hit = _route_names.get(key)
        if hit is None:
            if len(_route_names) > 8192:
                _route_names.clear()
            hit = _route_names[key] = original(self, request)
        return hit

    return _get_handler


def install() -> None:
    global _installed
    fr._IncludedRouter.matches = _matches  # type: ignore[method-assign]
    if not _installed:
        from prometheus_fastapi_instrumentator.middleware import PrometheusInstrumentatorMiddleware as P

        P._get_handler = _prometheus_handler(P._get_handler)  # type: ignore[method-assign]
        _installed = True


def uninstall_matching() -> None:
    """For the test: FastAPI's own matching again (install() puts it back)."""
    fr._IncludedRouter.matches = _original_matches  # type: ignore[method-assign]
