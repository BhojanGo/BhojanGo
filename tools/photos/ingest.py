"""Add the chosen food photos to the library.

    python tools/photos/ingest.py <picked.json> <dir of downloaded originals>

picked.json maps each slug to its Openverse record (title, creator, creator_url,
license, license_version, license_url, foreign_landing_url, url, provider) plus
"file", the original's file name in the given directory, and optionally "crop":
[left, top, right, bottom] as fractions, applied to the web versions only. Writes:
  docs/design/photos/originals/<slug>.<ext>      the original, as downloaded
  apps/web/public/food/<slug>-{1600,800,400}.webp  (never upscaled: a photo
      narrower than 1600 px keeps its own width in the -1600 file)
  docs/design/photos/LICENSES.md                 one row per photo
  docs/design/photos/contact-sheet.jpg           every photo with its slug
then regenerates the web credits (tools/photos/credits.py).
"""
import datetime
import json
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCS = os.path.join(ROOT, "docs", "design", "photos")
PUBLIC = os.path.join(ROOT, "apps", "web", "public", "food")
WIDTHS = (1600, 800, 400)
LICENSE_NAMES = {"cc0": "CC0 1.0", "pdm": "Public Domain Mark 1.0", "by": "CC BY", "by-sa": "CC BY-SA"}


def license_name(rec):
    name = LICENSE_NAMES[rec["license"]]
    if rec["license"] in ("by", "by-sa") and rec.get("license_version"):
        name += f" {rec['license_version']}"
    return name


def cell(text):
    return str(text or "").replace("|", "\\|").replace("\n", " ").strip()


def main(picked_path, src_dir):
    picked = json.load(open(picked_path, encoding="utf-8"))
    os.makedirs(os.path.join(DOCS, "originals"), exist_ok=True)
    os.makedirs(PUBLIC, exist_ok=True)
    today = datetime.date.today().isoformat()
    rows = []
    for slug in sorted(picked):
        rec = picked[slug]
        src = os.path.join(src_dir, rec["file"])
        ext = os.path.splitext(rec["file"])[1].lower().replace(".jpeg", ".jpg")
        shutil.copyfile(src, os.path.join(DOCS, "originals", slug + ext))
        im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
        if rec.get("crop"):
            l, t, r, b = rec["crop"]
            im = im.crop((round(l * im.width), round(t * im.height), round(r * im.width), round(b * im.height)))
        for w in WIDTHS:
            out = im if im.width <= w else im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
            out.save(os.path.join(PUBLIC, f"{slug}-{w}.webp"), "WEBP", quality=80, method=6)
        rows.append((slug, rec, Image.open(src).size, "Cropped, resized" if rec.get("crop") else "Resized"))
    with open(os.path.join(DOCS, "LICENSES.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("# Food photo licenses\n\n")
        f.write("Every photo in `originals/` and `apps/web/public/food/`. Found through the Openverse API "
                "(or Wikimedia Commons), commercial use and modification allowed. CC BY and CC BY-SA photos "
                "are credited on the website's /credits page, generated from this table by "
                "`python tools/photos/credits.py` (checked by `make ci`). Edit this table, then rerun it.\n\n")
        f.write("| Slug | Title | Source | Creator | License | License URL | Changes | Original size | Downloaded |\n")
        f.write("|---|---|---|---|---|---|---|---|---|\n")
        for slug, rec, (w, h), changes in rows:
            creator = cell(rec.get("creator")) or "Unknown"
            f.write(f"| {slug} | {cell(rec.get('title'))} | {rec['foreign_landing_url']} | {creator} | "
                    f"{license_name(rec)} | {rec['license_url']} | {changes} | {w}×{h} | {today} |\n")
    contact_sheet([r[0] for r in rows])
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "photos", "credits.py")], check=True)


def contact_sheet(slugs):
    tile, label, cols = 400, 34, 6
    rows = (len(slugs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tile, rows * (tile * 3 // 4 + label)), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    th = tile * 3 // 4
    for n, slug in enumerate(slugs):
        im = Image.open(os.path.join(PUBLIC, f"{slug}-400.webp"))
        im = ImageOps.fit(im, (tile - 8, th - 8))
        x, y = (n % cols) * tile, (n // cols) * (th + label)
        sheet.paste(im, (x + 4, y + 4))
        draw.text((x + 6, y + th + 4), slug, fill="black", font=font)
    sheet.save(os.path.join(DOCS, "contact-sheet.jpg"), quality=82)


if __name__ == "__main__":
    main(*sys.argv[1:3])
