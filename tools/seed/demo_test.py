"""Unit tests for the demo seed that need no database (make ci-guard; standard library only).

    python tools/seed/demo_test.py

- the demo seed refuses production (APP_ENV, ENVIRONMENT or Railway's name), and
  demo.py refuses before it imports a database driver, so before any DB access;
- the demo order history (demo_history.py): believable counts, ratings only on
  past orders, "New" kitchens below five ratings, times the kitchen was open;
- the demo riders: each city has the simulator's own pool (rider.sim.<city>.<n>,
  users.dispatch_pool "demo_sim") apart from the demo rider people test with
  (rider.demo.<city>, no pool), which keeps the history; phones never collide.
"""
import os
import re
import subprocess
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import demo_guard  # noqa: E402
import demo_history as h  # noqa: E402
import demo_data  # noqa: E402
from data import MARKETS, covers, dish_slug, menu_dishes  # noqa: E402
from demo_data import DEMO, ORDERS  # noqa: E402

NOW = datetime(2026, 11, 15, 18, 30)  # city local time


def city_covers(key: str) -> dict[str, str | None]:
    """A city's covers as the seeds give them: the base kitchens, then the demo kitchens (demo.py city_covers)."""
    market = next(m for m in MARKETS if m["key"] == key)
    kitchens = [(r["slug"], menu_dishes(r["menu"])) for r in market["restaurants"]]
    kitchens += [(k["slug"], menu_dishes(k["menu"])) for k in DEMO.get(key, {"kitchens": []})["kitchens"]]
    return covers(kitchens)


def shared_covers(assigned: dict[str, str | None]) -> dict[str, list[str]]:
    """Photo -> the kitchens that share it, for every photo used more than once (empty: all unique)."""
    by_photo: dict[str, list[str]] = {}
    for slug, photo in assigned.items():
        if photo:
            by_photo.setdefault(photo, []).append(slug)
    return {p: ks for p, ks in by_photo.items() if len(ks) > 1}


class CoverTests(unittest.TestCase):
    """R36: every kitchen in a city has its own cover photo (one of its own dishes, from the credited
    library), and no two kitchens in the same city share one."""

    ROOT = HERE.parent.parent

    def test_the_duplicate_check_fails_on_a_duplicate(self) -> None:
        self.assertEqual(shared_covers({"a": "pad-thai", "b": "pad-thai", "c": None}), {"pad-thai": ["a", "b"]})
        self.assertEqual(shared_covers({"a": "pad-thai", "b": "ramen"}), {})

    def test_every_kitchen_has_a_cover_and_none_is_shared(self) -> None:
        for m in MARKETS:
            assigned = city_covers(m["key"])
            with self.subTest(city=m["key"]):
                self.assertEqual([s for s, p in assigned.items() if not p], [], "kitchens with no cover of their own")
                self.assertEqual(shared_covers(assigned), {}, "kitchens in one city sharing a cover")

    def test_each_cover_is_one_of_its_dishes_and_its_files_exist(self) -> None:
        import json

        library = set(json.loads((self.ROOT / "apps/web/src/content/photo-library.json").read_text(encoding="utf-8")))
        menus = {r["slug"]: menu_dishes(r["menu"]) for m in MARKETS for r in m["restaurants"]}
        menus |= {k["slug"]: menu_dishes(k["menu"]) for c in DEMO.values() for k in c["kitchens"]}
        for m in MARKETS:
            for slug, photo in city_covers(m["key"]).items():
                with self.subTest(kitchen=slug):
                    self.assertIn(photo, library)
                    self.assertIn(photo, {dish_slug(d) for d in menus[slug]})
                    for w in (400, 800, 1600):
                        self.assertTrue((self.ROOT / f"apps/web/public/food/{photo}-{w}.webp").exists())


class GuardTests(unittest.TestCase):
    def test_production_names_are_refused(self) -> None:
        for env in ({"APP_ENV": "production"}, {"APP_ENV": " Prod "}, {"ENVIRONMENT": "production"},
                    {"ENVIRONMENT": "PROD"}, {"RAILWAY_ENVIRONMENT_NAME": "production"},
                    {"APP_ENV": "qa", "RAILWAY_ENVIRONMENT_NAME": "Production"},
                    {"APP_ENV": "development", "ENVIRONMENT": "production"}):
            self.assertIsNotNone(demo_guard.production_problem(env), env)
            with self.assertRaises(SystemExit) as e:
                demo_guard.refuse_production(env)
            self.assertIn("REFUSED", str(e.exception.code))

    def test_dev_and_qa_are_allowed(self) -> None:
        for env in ({}, {"APP_ENV": "development"}, {"APP_ENV": "qa", "RAILWAY_ENVIRONMENT_NAME": "qa"},
                    {"APP_ENV": "local", "ENVIRONMENT": "dev"}):
            self.assertIsNone(demo_guard.production_problem(env), env)
            demo_guard.refuse_production(env)  # no exit

    def test_demo_seed_refuses_before_touching_a_database(self) -> None:
        """demo.py run as the QA job and make seed run it: in production it stops at
        once, before importing SQLAlchemy or opening a connection (the DATABASE_URL
        here would hang or fail if it were ever used; CI has no SQLAlchemy at all)."""
        for var in ("APP_ENV", "ENVIRONMENT", "RAILWAY_ENVIRONMENT_NAME"):
            env = {k: v for k, v in os.environ.items() if k not in demo_guard.ENV_VARS}
            env |= {var: "production", "DATABASE_URL": "postgresql://demo:x@10.255.255.1:5432/prod",
                    "PYTHONPATH": ""}
            r = subprocess.run([sys.executable, str(HERE / "demo.py")], env=env, capture_output=True, text=True,
                               timeout=60)
            self.assertNotEqual(r.returncode, 0, var)
            self.assertIn("REFUSED", r.stderr, (var, r.stderr))
            self.assertNotIn("Traceback", r.stderr, (var, r.stderr))


class HistoryTests(unittest.TestCase):
    def plans(self, key: str) -> list:
        return h.plan_city(key, NOW.date(), NOW)

    def test_deterministic(self) -> None:
        for key in DEMO:
            self.assertEqual(self.plans(key), self.plans(key))

    def test_no_typed_ratings(self) -> None:
        for key, city in DEMO.items():
            for k in city["kitchens"]:
                self.assertNotIn("rating", k)
                self.assertNotIn("review_count", k)

    def test_counts_and_ratings_per_kitchen(self) -> None:
        for key, city in DEMO.items():
            plans = self.plans(key)
            news = 0
            for k in city["kitchens"]:
                mine = [p for p in plans if p.kitchen == k["slug"]]
                typed = sum(1 for o in ORDERS[key] if o[1] == k["slug"] and o[5])
                rated = [p for p in mine if p.review]
                stars = [p.review[0] for p in rated]
                self.assertTrue(all(1 <= s <= 5 for s in stars))
                self.assertLess(len(rated), len(mine) + 1)
                if k["new"]:
                    news += 1
                    self.assertTrue(1 <= len(mine) <= 6, (k["slug"], len(mine)))
                    self.assertLess(len(rated) + typed, h.MIN_RATINGS_FOR_STARS, k["slug"])
                    self.assertTrue(all(p.local.date() >= NOW.date() - timedelta(days=h.NEW_DAYS - 1) for p in mine))
                else:
                    self.assertTrue(5 <= len(mine) <= 60, (k["slug"], len(mine)))
                    self.assertGreaterEqual(len(rated) + typed, h.MIN_RATINGS_FOR_STARS, k["slug"])
                    self.assertLess(len(rated), len(mine), "not every order is rated")
                    self.assertGreater(sum(stars) / len(stars), 3.0, k["slug"])
            self.assertGreaterEqual(news, 1, f"{key}: some kitchens are new (fewer than five ratings)")
            counts = sorted(len([p for p in plans if p.kitchen == k["slug"]]) for k in city["kitchens"] if not k["new"])
            self.assertGreater(counts[-1] - counts[0], 15, "kitchens get different numbers of orders")

    def test_orders_are_placed_when_the_kitchen_was_open_and_are_done(self) -> None:
        for key, city in DEMO.items():
            kitchens = {k["slug"]: k for k in city["kitchens"]}
            service = h.service_hours(key)
            for p in self.plans(key):
                self.assertLessEqual(p.local, NOW - h.DONE_BEFORE)
                self.assertGreaterEqual(p.local, NOW - timedelta(days=h.HISTORY_DAYS + 15))
                minute = p.local.hour * 60 + p.local.minute
                windows = h.open_windows(kitchens[p.kitchen], p.local.weekday(), service)
                self.assertTrue(any(a <= minute <= b for a, b in windows), (p.kitchen, p.local))
                self.assertTrue(1 <= len(p.lines) <= 4)
                self.assertGreaterEqual(p.review_after, timedelta(minutes=20))

    def test_baskets_clear_the_minimum_order(self) -> None:
        for key, city in DEMO.items():
            kitchens = {k["slug"]: k for k in city["kitchens"]}
            for p in self.plans(key):
                k = kitchens[p.kitchen]
                prices = dict(h._dishes(k))
                total = sum(prices[name] * qty for name, qty, _ in p.lines)
                self.assertGreaterEqual(total, max(float(k["min_order"]), h.BASKET_FLOOR[key]), (p.kitchen, p.lines))

    def test_customers_are_demo_customers_near_the_kitchen(self) -> None:
        for key, city in DEMO.items():
            people = {c[0]: c for c in h.customers(key)}
            kitchens = {k["slug"]: k for k in city["kitchens"]}
            zones = h.live_zones(key)
            for c in h.regulars(key):
                self.assertTrue(c[0].startswith("regular") and c[0].endswith(f".{key}"))
                self.assertIsNotNone(h.zone_of((c[5], c[6]), zones), c)
            for p in self.plans(key):
                self.assertIn(p.customer, people)
                c, k = people[p.customer], kitchens[p.kitchen]
                self.assertLessEqual(h.haversine_km((k["lat"], k["lng"]), (c[5], c[6])), 7.0, (p.kitchen, p.customer))


class RiderPoolTests(unittest.TestCase):
    """Round 5, item 3: the simulator rides its own riders; people test with the demo rider."""

    SIM = re.compile(r"^rider\.sim\.([a-z0-9-]+)\.(\d+)@example\.com$")  # backend/worker/app/demo_sim/rules.py SIM_RIDER

    def test_each_city_has_a_simulator_pool_apart_from_the_demo_rider(self) -> None:
        for key, city in DEMO.items():
            pool = city["sim_riders"]
            self.assertTrue(2 <= len(pool) <= 3, key)
            for n, (email, name, _) in enumerate(pool, start=1):
                m = self.SIM.match(email)
                self.assertIsNotNone(m, email)
                self.assertEqual((m.group(1), int(m.group(2))), (key, n), email)
                self.assertEqual(len(name.split()), 2, "a believable full name")
            self.assertEqual(city["rider"][0], f"rider.demo.{key}@example.com")
            self.assertIsNone(self.SIM.match(city["rider"][0]), "the demo rider is never the simulator's")
            names = [city["rider"][1]] + [r[1] for r in pool]
            self.assertEqual(len(set(names)), len(names))
            self.assertEqual(demo_data.SIM_POOL, "demo_sim")

    def test_the_order_on_its_way_is_the_simulators_and_the_history_the_demo_riders(self) -> None:
        for key, city in DEMO.items():
            self.assertIn(demo_data.active_rider(key), [r[0] for r in city["sim_riders"]])
            self.assertNotEqual(demo_data.active_rider(key), city["rider"][0])
        source = (HERE / "demo.py").read_text(encoding="utf-8")
        self.assertIn('self.users[active_rider(key) if active else f"rider.{key}"]', source,
                      "past orders (the earnings screen) stay the demo rider's")
        self.assertIn("SIM_POOL", source)

    def test_seed_phones_never_collide(self) -> None:
        for m in MARKETS:
            key, prefix = m["key"], m["phone_prefix"]
            phones = [f"{prefix}900", *(f"{prefix}1{i:02d}" for i in range(1, len(m["customers"]) + 1)),
                      *(f"{prefix}2{i:02d}" for i in range(1, len(m["riders"]) + 1)),
                      *(f"{prefix}2{90 + i:02d}" for i in range(1, len(m.get("new_riders", [])) + 1))]
            if m.get("applicant"):
                phones.append(f"{prefix}901")
            city = DEMO.get(key)
            if city:
                phones += [f"{prefix}{p}" for _, _, p in [city["partner"], city["rider"], *city["sim_riders"]]]
                phones += [f"{prefix}{p}" for p in city["phones"].values()]
                phones += [f"{prefix}{r[8]}" for r in h.regulars(key)]
            self.assertEqual(len(phones), len(set(phones)), key)
            self.assertTrue(all(len(p) == len(phones[0]) for p in phones), key)


if __name__ == "__main__":
    unittest.main(verbosity=2)
