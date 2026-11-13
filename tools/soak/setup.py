"""People for the Boise dinner-rush soak (tools/soak), on top of `make seed`.

Boise's seed has 5 kitchens (one partner), 3 riders and 5 customers. The pilot
rehearsal wants 8 riders and enough customers that no one orders every few
minutes: this adds riders 4-8 (onboarding finished, like the seed's) and
customers 6-40 with home addresses around the seed customers' neighbourhoods.
Idempotent (the seed's upserts), so it can run before every soak.

    python tools/soak/setup.py      # in the soak container (DATABASE_URL set)
"""
import asyncio
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "seed"))
import seed  # noqa: E402  (tools/seed/seed.py: the same upserts as `make seed`)
from data import MARKETS  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

# Riders 4 and up (onboarding finished, like the seed's): five named, then numbered.
NAMES = ["Maya Patel", "Chris Walker", "Dana Kim", "Luis Ramirez", "Taylor Reed"]
TOTAL_RIDERS = int(os.environ.get("SOAK_RIDERS", "8"))
RIDERS = [NAMES[i] if i < len(NAMES) else f"Soak Rider {i + 4}" for i in range(max(0, TOTAL_RIDERS - 3))]
CUSTOMERS = int(os.environ.get("SOAK_CUSTOMERS", "40"))


async def main() -> None:
    m = next(x for x in MARKETS if x["key"] == "boi")
    rnd = random.Random(7)
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        for i, name in enumerate(RIDERS, start=len(m["riders"]) + 1):
            email = f"rider{i}.boi@example.com"
            rider_id = await seed.upsert_user(conn, email, name, "driver", m, f"{m['phone_prefix']}2{i:02d}")
            for kind in ("licence", "insurance", "background_check"):
                await conn.execute(seed.UPSERT_RIDER_DOC, {
                    "id": seed.sid("rider_document", email, kind), "rider_id": rider_id, "kind": kind,
                    "file_key": None if kind == "background_check" else f"rider_document/{rider_id}/seed-{kind}.jpg"})
        for i in range(len(m["customers"]) + 1, CUSTOMERS + 1):
            name, street, area, postal, lat, lng = rnd.choice(m["customers"])
            email = f"customer{i}.boi@example.com"
            user_id = await seed.upsert_user(conn, email, f"Soak Customer {i}", "customer", m, f"{m['phone_prefix']}3{i:02d}")
            await conn.execute(seed.UPSERT_ADDRESS, {
                "id": seed.sid("address", email, "home"), "user_id": user_id,
                "street": f"{100 + i} {street.split(' ', 1)[1]}, {area}", "city": m["city"], "state": m["state"],
                "postal_code": postal, "country": m["country"],
                "lat": lat + rnd.uniform(-0.006, 0.006), "lng": lng + rnd.uniform(-0.006, 0.006)})
        # The kitchens say how long they take (the bots cook 4-9 minutes); the batch engine
        # plans with the declared prep time, so it must be the real one.
        await conn.execute(text("UPDATE restaurants SET avg_prep_minutes = 8 WHERE city = 'Boise'"))
    await engine.dispose()
    print(f"soak people: riders 1-{len(m['riders']) + len(RIDERS)}, customers 1-{CUSTOMERS} in Boise")


if __name__ == "__main__":
    asyncio.run(main())
