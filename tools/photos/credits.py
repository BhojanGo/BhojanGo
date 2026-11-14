"""The website's photo credits, generated from docs/design/photos/LICENSES.md.

    python tools/photos/credits.py           write apps/web/src/content/photo-credits.json
    python tools/photos/credits.py --check   fail if that file is out of date (make ci)

Only photos whose license asks for attribution (CC BY, CC BY-SA) are listed;
CC0 and public-domain photos need none.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCE = os.path.join(ROOT, "docs", "design", "photos", "LICENSES.md")
TARGET = os.path.join(ROOT, "apps", "web", "src", "content", "photo-credits.json")


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


def main():
    text = credits()
    if "--check" in sys.argv:
        current = open(TARGET, encoding="utf-8").read() if os.path.exists(TARGET) else ""
        if current != text:
            sys.exit("photo-credits.json is out of date with docs/design/photos/LICENSES.md: "
                     "run python tools/photos/credits.py")
        print(f"photo credits up to date ({len(json.loads(text))} photos credited)")
        return
    os.makedirs(os.path.dirname(TARGET), exist_ok=True)
    with open(TARGET, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"wrote {os.path.relpath(TARGET, ROOT)} ({len(json.loads(text))} photos credited)")


if __name__ == "__main__":
    main()
