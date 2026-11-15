"""Side by side: the design (docs/design/web/r_<Page>.png) and the website's
screenshot of the same page, plus a rough "how different" score.

    python tools/web/design_compare.py <screenshots dir> <out dir>

For every <Page>.png in the screenshots dir that has a design r_<Page>.png, writes
<out>/<Page>.png (design left, website right, same width, labelled) and prints a
table. The score compares the two pages' layout, not their pixels: both are
scaled to 96 px wide and blurred, so different data (another kitchen's photo, a
longer name) barely moves it while a missing section, a different column count
or a different colour scheme does. Pages above NOTICEABLE are listed for review;
a person still judges them (docs/screenshots/web-v2/README.md).
"""
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageStat

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "docs" / "design" / "web"
NOTICEABLE = 0.11
PANEL = 720  # each side's width in the side-by-side image


def font(size: int) -> ImageFont.ImageFont:
    for name in ("arial.ttf", "DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def to_width(im: Image.Image, w: int) -> Image.Image:
    return im.resize((w, max(1, round(im.height * w / im.width))), Image.LANCZOS)


def score(a: Image.Image, b: Image.Image) -> float:
    """0 = same layout and colours, 1 = nothing alike (top part both have, 96 px wide)."""
    a, b = to_width(a.convert("RGB"), 96), to_width(b.convert("RGB"), 96)
    h = min(a.height, b.height)
    a, b = a.crop((0, 0, 96, h)).filter(ImageFilter.GaussianBlur(2)), b.crop((0, 0, 96, h)).filter(ImageFilter.GaussianBlur(2))
    diff = ImageStat.Stat(ImageChops.difference(a, b)).mean
    return round(sum(diff) / (3 * 255), 3)


def side_by_side(design: Image.Image, actual: Image.Image, title: str, s: float) -> Image.Image:
    d, a = to_width(design.convert("RGB"), PANEL), to_width(actual.convert("RGB"), PANEL)
    head = 44
    out = Image.new("RGB", (PANEL * 2 + 24, head + max(d.height, a.height)), "white")
    draw = ImageDraw.Draw(out)
    f = font(20)
    draw.text((8, 10), f"{title} — design", fill="black", font=f)
    draw.text((PANEL + 32, 10), f"website (score {s:.3f}{' — noticeably different' if s > NOTICEABLE else ''})",
              fill="#A3271F" if s > NOTICEABLE else "black", font=f)
    out.paste(d, (0, head))
    out.paste(a, (PANEL + 24, head))
    draw.line([(PANEL + 12, 0), (PANEL + 12, out.height)], fill="#C9D3D4", width=2)
    return out


def main(shots: str, out: str) -> int:
    src, dst = Path(shots), Path(out)
    dst.mkdir(parents=True, exist_ok=True)
    rows = []
    for shot in sorted(src.glob("*.png")):
        design = DESIGN / f"r_{shot.stem}.png"
        if not design.exists():
            continue
        d, a = Image.open(design), Image.open(shot)
        s = score(d, a)
        side_by_side(d, a, shot.stem, s).save(dst / f"{shot.stem}.png", optimize=True)
        rows.append((shot.stem, s))
    missing = sorted(p.stem[2:] for p in DESIGN.glob("r_*.png") if not (src / f"{p.stem[2:]}.png").exists())
    print(f"{'page':<18} score  verdict")
    for name, s in rows:
        print(f"{name:<18} {s:.3f}  {'NOTICEABLY DIFFERENT' if s > NOTICEABLE else 'close'}")
    if missing:
        print("no screenshot for:", ", ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
