"""The website's photo credits and the photo library list, generated from
docs/design/photos/LICENSES.md.

    python tools/photos/credits.py           write the files below
    python tools/photos/credits.py --check   fail if any is out of date (make ci-photos)

  apps/web/src/content/photo-credits.json            the /credits page: only photos whose
                                                      license asks for attribution (CC BY, CC BY-SA)
  backend/core_api/modules/markets/photo_library.json  every library slug: Markets checks a
                                                      country's hero photo against it
  apps/admin/src/content/photo-library.json          the same list, for the admin's "Hero dish" picker
  apps/admin/public/food/<slug>-400.webp             the picker's thumbnails (copies of the website's)
"""
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCE = os.path.join(ROOT, "docs", "design", "photos", "LICENSES.md")
TARGET = os.path.join(ROOT, "apps", "web", "src", "content", "photo-credits.json")
LIBRARY_TARGETS = [os.path.join(ROOT, "backend", "core_api", "modules", "markets", "photo_library.json"),
                   os.path.join(ROOT, "apps", "admin", "src", "content", "photo-library.json")]
WEB_FOOD = os.path.join(ROOT, "apps", "web", "public", "food")
ADMIN_FOOD = os.path.join(ROOT, "apps", "admin", "public", "food")
THUMB = 400


def rows():
    lines = [l for l in open(SOURCE, encoding="utf-8") if l.startswith("| ")]
    header = [c.strip() for c in lines[0].strip().strip("|").split(" | ")]
    for line in lines[1:]:
        cells = [c.strip().replace("\\|", "|") for c in line.strip()[2:-2].split(" | ")]
        yield dict(zip(header, cells))


def credits():
    out = []
    for r in rows():
        if r["License"].startswith(("CC BY", "CC BY-SA")):
            out.append({"slug": r["Slug"], "title": r["Title"], "source": r["Source"], "creator": r["Creator"],
                        "license": r["License"], "licenseUrl": r["License URL"], "changes": r["Changes"]})
    return json.dumps(out, indent=2, ensure_ascii=False) + "\n"


def library() -> str:
    """Every photo in the library (sorted slugs); each must exist on the website in all sizes."""
    slugs = sorted(r["Slug"] for r in rows())
    for slug in slugs:
        for w in (400, 800, 1600):
            if not os.path.exists(os.path.join(WEB_FOOD, f"{slug}-{w}.webp")):
                sys.exit(f"LICENSES.md lists {slug} but apps/web/public/food/{slug}-{w}.webp is missing")
    return json.dumps(slugs, indent=2) + "\n"


def _read(path: str) -> str:
    return open(path, encoding="utf-8").read() if os.path.exists(path) else ""


def _bytes(path: str) -> bytes:
    return open(path, "rb").read() if os.path.exists(path) else b""


def thumbs(slugs: list[str]) -> dict[str, str]:
    """admin thumbnail path -> website source path."""
    return {os.path.join(ADMIN_FOOD, f"{s}-{THUMB}.webp"): os.path.join(WEB_FOOD, f"{s}-{THUMB}.webp") for s in slugs}


def main():
    text = credits()
    lib = library()
    slugs = json.loads(lib)
    pairs = thumbs(slugs)
    if "--check" in sys.argv:
        if _read(TARGET) != text:
            sys.exit("photo-credits.json is out of date with docs/design/photos/LICENSES.md: "
                     "run python tools/photos/credits.py")
        for t in LIBRARY_TARGETS:
            if _read(t) != lib:
                sys.exit(f"{os.path.relpath(t, ROOT)} is out of date with docs/design/photos/LICENSES.md: "
                         "run python tools/photos/credits.py")
        names = {os.path.basename(p) for p in pairs}
        extra = set(os.listdir(ADMIN_FOOD)) - names if os.path.isdir(ADMIN_FOOD) else set()
        stale = [p for p, src in pairs.items() if _bytes(p) != _bytes(src)]
        if stale or extra:
            sys.exit(f"apps/admin/public/food is out of date ({len(stale)} missing or changed, {len(extra)} extra): "
                     "run python tools/photos/credits.py")
        print(f"photo credits up to date ({len(json.loads(text))} photos credited, {len(slugs)} in the library)")
        return
    for path, body in [(TARGET, text)] + [(t, lib) for t in LIBRARY_TARGETS]:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        print(f"wrote {os.path.relpath(path, ROOT)}")
    os.makedirs(ADMIN_FOOD, exist_ok=True)
    for name in os.listdir(ADMIN_FOOD):
        if os.path.join(ADMIN_FOOD, name) not in pairs:
            os.remove(os.path.join(ADMIN_FOOD, name))
    for dst, src in pairs.items():
        shutil.copyfile(src, dst)
    print(f"{len(json.loads(text))} photos credited, {len(slugs)} in the library, thumbnails in apps/admin/public/food")


if __name__ == "__main__":
    main()
