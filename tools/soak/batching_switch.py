"""Turn live batching on or off for a city, the way an admin does it in
Pricing & Rules -> Business rules (a new version of the city's `batching` rule;
business rules go live without a second approval).

    python tools/soak/batching_switch.py on|off [US-ID-BOI]     # in the soak container
"""
import os
import sys

import httpx

CORE = os.environ.get("SOAK_CORE", "http://core-api:8001") + "/api/v1"
ADMIN = ("cm.us@example.com", "BhojanGoAdmin1")  # USA country manager


def main(state: str, city: str = "US-ID-BOI") -> None:
    live = state == "on"
    with httpx.Client(timeout=30) as c:
        r = c.post(f"{CORE}/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]})
        r.raise_for_status()
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        rules = c.get(f"{CORE}/rules", headers=h, params={"family": "business"}).json()
        rule = next(x for x in rules if x["template"] == "batching" and x["market_scope"] == city
                    and x["status"] == "published" and not x.get("effective_to"))
        if bool(rule["params"].get("live")) == live:
            print(f"batching in {city} is already {state}")
            return
        r = c.post(f"{CORE}/rules/{rule['id']}/versions", headers=h, json={"params": {**rule["params"], "live": live}})
        r.raise_for_status()
        r = c.post(f"{CORE}/rules/{r.json()['id']}/submit", headers=h)  # business rules go live on submit
        r.raise_for_status()
        print(f"batching in {city}: {state} (rule version {r.json().get('version')}, {r.json().get('status')})")


if __name__ == "__main__":
    main(*sys.argv[1:])
