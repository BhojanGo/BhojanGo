"""Unit tests for the markets-only seed's data (markets_data.py) and the full seed's production
refusal; no database (make ci-guard; standard library only). The seed itself runs on a fresh
database in CI (backend-checks.yml, core_api/integration/test_markets_only_seed.py).

    python tools/seed/markets_test.py
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import markets_data as md  # noqa: E402
from data import COUNTRIES, RULES  # noqa: E402


class MarketsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ms = md.markets()

    def test_boise_is_the_only_open_city(self) -> None:
        statuses = md.city_statuses(self.ms)
        self.assertEqual([c for c, s in statuses.items() if s in md.OPEN], ["US-ID-BOI"])
        self.assertEqual(statuses["US-ID-BOI"], "live")
        self.assertEqual(statuses["IN-TG-HYD"], "draft")

    def test_india_is_kept_but_switched_off(self) -> None:
        india = next(c for c in self.ms if c["code"] == "IN")
        self.assertEqual(india["status"], "draft")
        self.assertTrue(all(r["status"] == "draft" for r in india["regions"]))
        hyd = next(city for r in india["regions"] for city in r["cities"] if city["code"] == "IN-TG-HYD")
        self.assertTrue(hyd["zones"])
        self.assertTrue(all(z[3] == "draft" for z in hyd["zones"]))

    def test_the_us_and_idaho_are_open_with_boise_zones(self) -> None:
        us = next(c for c in self.ms if c["code"] == "US")
        idaho = us["regions"][0]
        self.assertEqual((us["status"], idaho["status"]), ("live", "live"))
        boise = next(c for c in idaho["cities"] if c["code"] == "US-ID-BOI")
        self.assertTrue(boise["zones"])

    def test_legal_entity_names(self) -> None:
        self.assertEqual(md.legal_entities(self.ms),
                         {"IN": "DeepTrics Software Solutions Pvt Ltd", "US": "DeepTrics LLC"})

    def test_the_base_seed_data_is_unchanged(self) -> None:
        self.assertEqual(md.city_statuses(COUNTRIES)["US-ID-BOI"], "beta")
        self.assertEqual(md.city_statuses(COUNTRIES)["IN-TG-HYD"], "live")

    def test_rules_are_market_rules_only(self) -> None:
        rules = md.rules()
        self.assertTrue(rules)
        self.assertFalse([r for r in rules if r[4] == "restaurant" or r[0] == "promotion"])
        keyed = {(r[0], r[1], r[4], r[5]): r[6] for r in rules}
        # Boise: 15% commission on every tier
        self.assertEqual(set(keyed[("commission", "percent_by_tier", "country", "US")]["tiers"].values()), {15})
        # India's R16 tax rules and both payment fee rules are kept
        for family, template, level, scope in (("business", "commission_tax", "country", "IN"),
                                               ("business", "payout_tds", "country", "IN"),
                                               ("tax", "rate_on_lines", "country", "IN"),
                                               ("business", "payment_fees", "country", "US"),
                                               ("business", "payment_fees", "country", "IN"),
                                               ("tax", "external", "country", "US")):
            self.assertIn((family, template, level, scope), keyed)
        self.assertEqual(len(rules), len([r for r in RULES if r[4] != "restaurant" and r[0] != "promotion"]))


class FullSeedRefusesProduction(unittest.TestCase):
    def test_full_seed_refuses_before_any_database_import(self) -> None:
        for env in ({"APP_ENV": "production"}, {"RAILWAY_ENVIRONMENT_NAME": "production"}):
            p = subprocess.run([sys.executable, str(HERE / "seed.py")], capture_output=True, text=True,
                               env={**os.environ, "APP_ENV": "", "RAILWAY_ENVIRONMENT_NAME": "", **env,
                                    "DATABASE_URL": "postgresql+asyncpg://x:y@localhost:1/z"}, timeout=60)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("REFUSED", p.stderr)
            self.assertIn("markets.py", p.stderr)


if __name__ == "__main__":
    unittest.main()
