"""Demo data never goes near production (tools/seed/demo.py; standard library only).

Every entry point of the demo seed calls ``refuse_production()`` before it opens a
database connection (demo.py does it before it even imports a database driver),
so it is tested without one: tools/seed/demo_test.py, in make ci-guard.
Production ratings only ever come from real delivered orders.
"""
import os
import sys
from collections.abc import Mapping

# shared/config.py PRODUCTION_NAMES; ENVIRONMENT is the generic name some hosts set.
PRODUCTION = frozenset({"production", "prod"})
ENV_VARS = ("APP_ENV", "ENVIRONMENT", "RAILWAY_ENVIRONMENT_NAME")


def production_problem(env: Mapping[str, str] | None = None) -> str | None:
    """Why this process looks like production, or None."""
    env = os.environ if env is None else env
    for var in ENV_VARS:
        value = env.get(var, "")
        if value.strip().lower() in PRODUCTION:
            return f"{var}={value!r}"
    return None


def refuse_production(env: Mapping[str, str] | None = None, what: str = "demo seed") -> None:
    problem = production_problem(env)
    if problem:
        sys.exit(f"{what}: REFUSED: {problem}. Demo data is for make dev and QA only, never production.")
