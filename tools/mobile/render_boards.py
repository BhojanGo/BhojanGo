"""Render the app design boards (docs/design/screens/{Customer,Rider,Partner}*.html) to
r_<Board>.png at their own frame size, for tools/mobile/screens_compose.py.

    python tools/mobile/render_boards.py <repo root> <out dir>   (CHROMIUM= an installed Chrome, optional)
"""
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(sys.argv[1])
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
boards = sorted(p for p in (ROOT / "docs/design/screens").glob("*.html")
                if p.stem.startswith(("Customer", "Rider", "Partner")))
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=os.environ.get("CHROMIUM") or None)
    page = b.new_page(viewport={"width": 1400, "height": 1000})
    for f in boards:
        page.goto(f.as_uri(), wait_until="networkidle")
        page.wait_for_timeout(800)
        frame = page.locator("body div[style*='width:'][style*='height:']").first
        box = frame.bounding_box()
        frame.screenshot(path=str(OUT / f"r_{f.stem}.png"))
        print(f.stem, int(box["width"]), "x", int(box["height"]))
    b.close()
