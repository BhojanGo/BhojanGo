"""Turn live batching on or off for a city, the way admins do it in
Pricing & Rules -> Business rules: a new version of the city's `batching` rule,
submitted by the country manager and approved by Finance (it changes rider pay).

    python tools/soak/batching_switch.py on|off [US-ID-BOI]     # in the soak container
"""
import os
import sys

import httpx

CORE = os.environ.get("SOAK_CORE", "http://core-api:8001") + "/api/v1"

# Tests never write to QA or production (tools/target_guard.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from target_guard import ensure_safe_api  # noqa: E402

ensure_safe_api(CORE)
ADMIN = ("cm.us@example.com", "BhojanGoAdmin1")  # USA country manager (makes the change)
APPROVER = ("finance.us@example.com", "BhojanGoAdmin1")  # a second admin approves it
ADMINS = {"US": (ADMIN, APPROVER), "IN": (("cm.in@example.com", "BhojanGoAdmin1"), ("finance.in@example.com", "BhojanGoAdmin1"))}


def main(state: str, city: str = "US-ID-BOI") -> None:
    live = state == "on"
    admin, approver = ADMINS[city[:2]]
    with httpx.Client(timeout=30) as c:
        from totp_signin import finish  # admins: the second step (seed key)

        def post(path: str, data: dict) -> dict:
            res = c.post(f"{CORE}{path}", json=data)
            res.raise_for_status()
            return res.json()

        body = finish(post, admin[0], post("/auth/login", {"email": admin[0], "password": admin[1]}))
        h = {"Authorization": f"Bearer {body['access_token']}"}
        rules = c.get(f"{CORE}/rules", headers=h, params={"family": "business"}).json()
        rule = next(x for x in rules if x["template"] == "batching" and x["market_scope"] == city
                    and x["status"] == "published" and not x.get("effective_to"))
        if bool(rule["params"].get("live")) == live:
            print(f"batching in {city} is already {state}")
            return
        r = c.post(f"{CORE}/rules/{rule['id']}/versions", headers=h, json={"params": {**rule["params"], "live": live}})
        r.raise_for_status()
        vid = r.json()["id"]
        r = c.post(f"{CORE}/rules/{vid}/submit", headers=h)  # batching changes rider pay: a second admin approves
        r.raise_for_status()
        if r.json()["status"] == "pending_approval":
            fin = finish(post, approver[0], post("/auth/login", {"email": approver[0], "password": approver[1]}))
            r = c.post(f"{CORE}/rules/{vid}/approve", headers={"Authorization": f"Bearer {fin['access_token']}"},
                       json={"note": "soak run"})
            r.raise_for_status()
        print(f"batching in {city}: {state} (rule version {r.json().get('version')}, {r.json().get('status')})")


if __name__ == "__main__":
    main(*sys.argv[1:])
