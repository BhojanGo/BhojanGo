"""Fetch DB-IP's free "IP to City Lite" database (CC BY 4.0, no account, monthly)
for the website's "Looks like you're near ..." hint (shared/geoip.py).

    python tools/geoip_fetch.py /srv/geoip/dbip-city-lite.mmdb

Tries this month's file, then last month's. Failing is fine: no file, no hint
(the website falls back to the browser's locale). Attribution: /credits.
"""
import datetime
import gzip
import shutil
import sys
import urllib.request
from pathlib import Path

URL = "https://download.db-ip.com/free/dbip-city-lite-{ym}.mmdb.gz"


def main(target: str) -> int:
    out = Path(target)
    out.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().replace(day=1)
    for month in (today, (today - datetime.timedelta(days=1)).replace(day=1)):
        url = URL.format(ym=month.strftime("%Y-%m"))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "bhojango-geoip-fetch"})
            with urllib.request.urlopen(req, timeout=120) as r, gzip.GzipFile(fileobj=r) as gz, open(out, "wb") as f:
                shutil.copyfileobj(gz, f)
            print(f"geoip: {url} -> {out} ({out.stat().st_size // 1_000_000} MB)")
            return 0
        except Exception as e:  # noqa: BLE001 - optional data, never fail the build
            print(f"geoip: {url} not available ({e})")
    out.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
