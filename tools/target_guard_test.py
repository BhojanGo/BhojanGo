"""Unit tests for tools/target_guard.py (make ci-guard; standard library only).

    python tools/target_guard_test.py
"""
import sys
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import target_guard as g  # noqa: E402


def health(env: str | None):  # type: ignore[no-untyped-def]
    def fetch(url: str) -> dict:
        assert url.endswith("/health"), url
        return {"status": "healthy"} | ({"environment": env} if env is not None else {})
    return fetch


def unreachable(url: str) -> dict:
    raise urllib.error.URLError("connection refused")


class ProcessTests(unittest.TestCase):
    def test_local_development_is_allowed(self) -> None:
        for url in ("postgresql+asyncpg://bhojango:x@postgres:5432/bhojango",
                    "postgresql+asyncpg://bhojango:x@localhost:5432/bhojango",
                    "postgresql://u:p@127.0.0.1/db", "postgresql://u:p@[::1]:5432/db", ""):
            self.assertIsNone(g.process_problem({"APP_ENV": "development", "DATABASE_URL": url}), url)
        self.assertIsNone(g.process_problem({}))

    def test_qa_and_production_names_are_refused(self) -> None:
        for env in ({"APP_ENV": "qa"}, {"APP_ENV": "QA "}, {"APP_ENV": "production"}, {"APP_ENV": "prod"},
                    {"APP_ENV": "development", "RAILWAY_ENVIRONMENT_NAME": "QA"},
                    {"RAILWAY_ENVIRONMENT_NAME": "production"}):
            self.assertIsNotNone(g.process_problem(env), env)
        self.assertIsNone(g.process_problem({"APP_ENV": "staging", "RAILWAY_ENVIRONMENT_NAME": "staging"}))

    def test_hosted_database_is_refused_even_without_env_names(self) -> None:
        # qa-job.sh's old integration job unset APP_ENV and RAILWAY_ENVIRONMENT_NAME: the host still gives it away.
        for url in ("postgresql+asyncpg://bhojango:x@postgres.railway.internal:5432/bhojango_it",
                    "postgresql://u:p@db.example.com/x", "postgresql://u:p@10.0.0.5/x"):
            p = g.process_problem({"DATABASE_URL": url})
            self.assertIsNotNone(p, url)

    def test_ensure_exits_non_zero(self) -> None:
        with self.assertRaises(SystemExit) as e:
            g.ensure_local_process({"APP_ENV": "qa"})
        self.assertEqual(e.exception.code, g.REFUSED_EXIT)
        g.ensure_local_process({"APP_ENV": "test"})  # no exception


class ApiTests(unittest.TestCase):
    def test_reported_environment_decides(self) -> None:
        self.assertIsNone(g.api_problem("http://core-api:8001", health("development")))
        self.assertIsNone(g.api_problem("https://core-api-staging.up.railway.app", health("staging")))
        for env in ("qa", "QA", "production", "prod"):
            self.assertIsNotNone(g.api_problem("https://core-api-x.up.railway.app/api/v1", health(env)), env)
            self.assertIsNotNone(g.api_problem("http://localhost:8001", health(env)), env)

    def test_silent_hosted_target_is_refused_silent_local_one_allowed(self) -> None:
        self.assertIsNotNone(g.api_problem("https://core-api-qa.up.railway.app", health(None)))
        self.assertIsNone(g.api_problem("http://core-api:8001/api/v1", health(None)))
        self.assertIsNone(g.api_problem("http://localhost:8001", health(None)))

    def test_unreachable_or_odd_targets_are_refused(self) -> None:
        self.assertIsNotNone(g.api_problem("http://core-api:8001", unreachable))
        self.assertIsNotNone(g.api_problem("ftp://core-api", health("development")))
        self.assertIsNotNone(g.api_problem("", health("development")))

    def test_health_url_strips_the_api_prefix(self) -> None:
        seen: list[str] = []
        g.api_problem("http://core-api:8001/api/v1/", lambda u: seen.append(u) or {"environment": "development"})
        self.assertEqual(seen, ["http://core-api:8001/health"])

    def test_ensure_safe_api_and_cli(self) -> None:
        with self.assertRaises(SystemExit) as e:
            g.ensure_safe_api("http://core-api:8001", "https://qa.example.app", fetch=lambda u: (
                {"environment": "qa"} if "qa." in u else {"environment": "development"}))
        self.assertEqual(e.exception.code, g.REFUSED_EXIT)
        self.assertEqual(g.main(["nonsense"]), 2)


if __name__ == "__main__":
    unittest.main()
