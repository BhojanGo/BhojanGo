"""Side-by-sides for the app screenshots (docs/screenshots/apps-v2).

    python tools/mobile/screens_compose.py <raw dir> <boards dir> <out dir>

<raw dir> holds the Maestro flows' screenshots (read-only on QA; stack-* ones from the
throwaway stack, .github/workflows/app-screens.yml), one folder per app and
device (customer-phone, rider-phone, partner-phone, partner-tablet), as Maestro
writes them (`takeScreenshot`). <boards dir> holds the design boards rendered to
r_<Board>.png (docs/design/screens/*.html). For every screenshot this writes a
JPEG copy under <out>/<app>-<device>/, and for each board in PAIRS a side-by-side
<out>/<Board>.jpg: the board on the left, the app's screen on the right, same height.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# design board -> (folder, screenshot name without .png): the app screen that shows the same thing
PAIRS = {
    "CustomerSignIn": ("customer-phone", "01-sign-in"),
    "CustomerOTP": ("customer-phone", "02-code"),
    "CustomerHome": ("customer-phone", "qa-01-home"),
    "CustomerMenu": ("customer-phone", "qa-02-kitchen"),
    "CustomerCheckout": ("customer-phone", "qa-04-bag"),
    "CustomerTracking": ("customer-phone", "qa-05-tracking"),
    "RiderOffer": ("rider-phone", "02-demo-order"),
    "RiderDropoff": ("rider-phone", "00-delivery-opened"),
    "RiderEarnings": ("rider-phone", "03-earnings"),
    "PartnerOrders": ("partner-tablet", "02-rating-chip"),  # the orders board, with the rating chip in its header
    "PartnerMenu": ("partner-tablet", "03-menu"),
    # States QA can't show (they write data): taken on a throwaway stack on GitHub Actions
    # (.github/workflows/app-screens.yml, flows in apps/<app>/.maestro/stack/), named stack-*.
    "CustomerLoading": ("customer-phone", "stack-loading"),
    "CustomerOutOfArea": ("customer-phone", "stack-out-of-area"),
    "CustomerPaymentFailed": ("customer-phone", "stack-payment-failed"),
    "RiderOnboarding": ("rider-phone", "stack-onboarding"),
    "PartnerOnboarding": ("partner-tablet", "stack-onboarding"),
}
HEIGHT = 1200


def font(size: int):  # type: ignore[no-untyped-def]
    for name in ("arial.ttf", "DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def fit(im: Image.Image) -> Image.Image:
    return im.resize((max(1, round(im.width * HEIGHT / im.height)), HEIGHT))


def main() -> None:
    raw, boards, out = (Path(a) for a in sys.argv[1:4])
    out.mkdir(parents=True, exist_ok=True)
    shots: dict[tuple[str, str], Path] = {}
    for folder in sorted(p for p in raw.iterdir() if p.is_dir()):
        dest = out / folder.name
        dest.mkdir(exist_ok=True)
        for png in sorted(folder.glob("*.png")):
            Image.open(png).convert("RGB").save(dest / f"{png.stem}.jpg", quality=82, optimize=True)
            shots[(folder.name, png.stem)] = png
    made, missing = [], []
    for board, key in PAIRS.items():
        b, s = boards / f"r_{board}.png", shots.get(key)
        if not b.exists() or s is None:
            missing.append(f"{board} <- {key[0]}/{key[1]}")
            continue
        left, right = fit(Image.open(b).convert("RGB")), fit(Image.open(s).convert("RGB"))
        head, gap = 40, 24
        canvas = Image.new("RGB", (left.width + gap + right.width, HEIGHT + head), "white")
        d = ImageDraw.Draw(canvas)
        d.text((6, 10), f"Design: {board}", fill="#111418", font=font(20))
        where = "App on a throwaway stack" if key[1].startswith("stack-") else "App on QA"
        d.text((left.width + gap + 6, 10), f"{where}: {key[0]} / {key[1]}", fill="#111418", font=font(20))
        canvas.paste(left, (0, head))
        canvas.paste(right, (left.width + gap, head))
        canvas.save(out / f"{board}.jpg", quality=82, optimize=True)
        made.append(board)
    print(f"{len(shots)} screens; side-by-sides: {', '.join(made)}")
    if missing:
        print("no pair for: " + "; ".join(missing))


if __name__ == "__main__":
    main()
