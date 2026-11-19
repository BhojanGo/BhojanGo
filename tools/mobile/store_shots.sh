#!/bin/bash
# Store screenshots from an Android emulator (docs/launch/store/screenshots.md).
#
#   tools/mobile/store_shots.sh --app <customer|kitchen|delivery> --out <dir> [options]
#
# Options:
#   --serial S        adb serial (default emulator-5554; ANDROID_SERIAL is ignored).
#                     ZY22FDFV9J and emulator-5556 are refused, and so is any device
#                     that is not an emulator.
#   --flow F.yaml     Maestro flow to run; its takeScreenshot files are collected.
#                     Repeat for several flows. Without --flow: manual mode.
#   --names "a b c"   Manual mode: the screens to capture, in order (default per app).
#   --targets LIST    Comma list of sizes (default: play-phone,ios69,ios65, plus
#                     play7,play10,ipad13 for kitchen). "none" keeps only raw files.
#   --crop-top N      Pixels to cut from the top of each capture (status bar).
#   --crop-bottom N   Pixels to cut from the bottom (navigation bar).
#                     Apple refuses screenshots with Android system bars (2.3.10).
#   --pad RRGGBB      Background for padding (default F4F6F6; delivery 0C1416).
#   --launch          Start the app before capturing.
#   --demo-bar        Clean status bar (Android System UI demo mode) while capturing.
#
# Writes <out>/raw/<name>.png as captured and <out>/<target>/<name>.png sized.
# Sizing uses Python with Pillow; without it only raw files are written.
#
# The script talks only to adb and (with --flow) Maestro. It does not start an
# emulator, build the app or change the backend. Flows that place orders or change
# state must run against a local stack, never QA or production. Use a production
# build (EXPO_PUBLIC_APP_ENV=production) so the "Test site" banner is not captured.
set -u

die() { echo "store_shots: $*" >&2; exit 2; }

SERIAL="emulator-5554"
APP=""
OUT=""
FLOWS=()
NAMES=""
TARGETS=""
CROP_TOP=0
CROP_BOTTOM=0
PAD=""
LAUNCH=0
DEMO_BAR=0

while [ $# -gt 0 ]; do
  case "$1" in
    --serial) SERIAL="${2:?--serial needs a value}"; shift 2 ;;
    --app) APP="${2:?--app needs a value}"; shift 2 ;;
    --out) OUT="${2:?--out needs a value}"; shift 2 ;;
    --flow) FLOWS+=("${2:?--flow needs a file}"); shift 2 ;;
    --names) NAMES="${2:?--names needs a value}"; shift 2 ;;
    --targets) TARGETS="${2:?--targets needs a value}"; shift 2 ;;
    --crop-top) CROP_TOP="${2:?}"; shift 2 ;;
    --crop-bottom) CROP_BOTTOM="${2:?}"; shift 2 ;;
    --pad) PAD="${2:?}"; shift 2 ;;
    --launch) LAUNCH=1; shift ;;
    --demo-bar) DEMO_BAR=1; shift ;;
    -h|--help) awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "$0"; exit 0 ;;
    *) die "unknown option: $1 (see --help)" ;;
  esac
done

[ -n "$APP" ] || die "--app is required (customer | kitchen | delivery)"
[ -n "$OUT" ] || die "--out is required"
case "$CROP_TOP$CROP_BOTTOM" in *[!0-9]*) die "--crop-top and --crop-bottom take whole pixels" ;; esac

# ── the device: never the two protected serials, only an emulator ───────────────
case "$(printf '%s' "$SERIAL" | tr '[:lower:]' '[:upper:]')" in
  ZY22FDFV9J|EMULATOR-5556) die "refusing serial $SERIAL: this device must not be touched" ;;
esac
unset ANDROID_SERIAL  # every adb call below names the serial itself
command -v adb >/dev/null 2>&1 || die "adb not found on PATH"
state="$(adb -s "$SERIAL" get-state 2>/dev/null | tr -d '\r')"
[ "$state" = "device" ] || die "$SERIAL is not connected (state: ${state:-none}); this script does not start emulators"
qemu="$(adb -s "$SERIAL" shell getprop ro.kernel.qemu 2>/dev/null | tr -d '\r')"
qemu2="$(adb -s "$SERIAL" shell getprop ro.boot.qemu 2>/dev/null | tr -d '\r')"
case "$SERIAL" in
  emulator-*) : ;;
  *) [ "$qemu" = "1" ] || [ "$qemu2" = "1" ] || die "$SERIAL is not an emulator; refusing" ;;
esac

# ── the app ──────────────────────────────────────────────────────────────────────
case "$APP" in
  customer)
    PKG=com.bhojango.app; DEF_PAD=F4F6F6; DEF_TARGETS=play-phone,ios69,ios65
    DEF_NAMES="01-home 02-kitchen 03-dish 04-bag 05-tracking 06-messages 07-orders 08-sign-in" ;;
  kitchen|partner)
    APP=kitchen; PKG=com.bhojango.partner; DEF_PAD=F4F6F6; DEF_TARGETS=play-phone,play7,play10,ios69,ios65,ipad13
    DEF_NAMES="01-orders-new 02-preparing-ready 03-menu 04-dish-photo 05-offers 06-ratings 07-payouts 08-help" ;;
  delivery|rider)
    APP=delivery; PKG=com.bhojango.rider; DEF_PAD=0C1416; DEF_TARGETS=play-phone,ios69,ios65
    DEF_NAMES="01-online 02-offer 03-batch-offer 04-pickup 05-dropoff 06-earnings 07-sign-up 08-safety" ;;
  *) die "unknown app: $APP (customer | kitchen | delivery)" ;;
esac
NAMES="${NAMES:-$DEF_NAMES}"
TARGETS="${TARGETS:-$DEF_TARGETS}"
PAD="${PAD:-$DEF_PAD}"
case "$PAD" in [0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]) : ;; *) die "--pad takes RRGGBB" ;; esac

adb -s "$SERIAL" shell pm path "$PKG" 2>/dev/null | grep -q "package:" || die "$PKG is not installed on $SERIAL"

RAW="$OUT/raw"
mkdir -p "$RAW" || die "cannot create $RAW"

# ── optional clean status bar (restored on exit) ────────────────────────────────
demo() { adb -s "$SERIAL" shell am broadcast -a com.android.systemui.demo -e command "$@" >/dev/null 2>&1; }
cleanup() {
  if [ "$DEMO_BAR" = 1 ]; then demo exit; fi
}
trap cleanup EXIT
if [ "$DEMO_BAR" = 1 ]; then
  adb -s "$SERIAL" shell settings put global sysui_demo_allowed 1 >/dev/null 2>&1
  demo enter
  demo clock -e hhmm 0941
  demo battery -e level 100 -e plugged false
  demo network -e wifi show -e level 4
  demo network -e mobile show -e datatype none -e level 4
  demo notifications -e visible false
fi

if [ "$LAUNCH" = 1 ]; then
  adb -s "$SERIAL" shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1 \
    || echo "store_shots: could not launch $PKG" >&2
fi

shot() {  # shot <name>: one PNG from the device
  local f="$RAW/$1.png"
  adb -s "$SERIAL" exec-out screencap -p > "$f" 2>/dev/null
  if [ -s "$f" ] && [ "$(head -c 4 "$f" | tail -c 3)" = "PNG" ]; then
    echo "captured $f"
  else
    rm -f "$f"; echo "store_shots: capture of $1 failed" >&2; return 1
  fi
}

banner_check() {  # warn when the test-site banner is on screen (testID test-banner)
  if adb -s "$SERIAL" exec-out uiautomator dump /dev/tty 2>/dev/null | grep -q 'test-banner'; then
    echo "store_shots: WARNING: the 'Test site' banner is on screen; use a production build" >&2
  fi
}

# ── capture ──────────────────────────────────────────────────────────────────────
if [ "${#FLOWS[@]}" -gt 0 ]; then
  command -v maestro >/dev/null 2>&1 || die "maestro not found on PATH"
  WORK="$RAW/maestro"
  mkdir -p "$WORK"
  MARK="$WORK/.started"; : > "$MARK"
  echo "store_shots: Maestro flows run against whatever backend the installed build uses."
  echo "store_shots: flows that place orders or change state must use a local stack only."
  for flow in "${FLOWS[@]}"; do
    [ -f "$flow" ] || die "no such flow: $flow"
    abs="$(cd "$(dirname "$flow")" && pwd)/$(basename "$flow")"
    echo "== maestro $(basename "$flow") on $SERIAL"
    # takeScreenshot paths are relative to the working directory: keep them under $WORK.
    (cd "$WORK" && timeout 900 maestro --device "$SERIAL" test "$abs") || echo "store_shots: flow failed: $flow (keeping any shots it took)" >&2
  done
  # Flatten every PNG the flows wrote into raw/<basename>.png. Some Maestro versions
  # write takeScreenshot files into their run folder (~/.maestro/tests/<run>/) instead
  # of the working directory: take those from this run too, but not the automatic
  # failure screenshots.
  { find "$WORK" -name '*.png' -type f 2>/dev/null
    [ -d "$HOME/.maestro/tests" ] && find "$HOME/.maestro/tests" -name '*.png' -type f -newer "$MARK" 2>/dev/null | grep -v 'screenshot-'
  } | while read -r f; do
    cp "$f" "$RAW/$(basename "$f")" && echo "collected $RAW/$(basename "$f")"
  done
else
  echo "Manual mode on $SERIAL ($PKG). For each screen: open it in the app, then"
  echo "press Enter to capture, s then Enter to skip, q then Enter to stop."
  for name in $NAMES; do
    printf '%s> ' "$name"
    read -r answer < /dev/tty || answer=q
    case "$answer" in
      q|Q) break ;;
      s|S) continue ;;
    esac
    banner_check
    shot "$name"
  done
fi

# ── size for the stores ──────────────────────────────────────────────────────────
[ "$TARGETS" = "none" ] && { echo "raw captures in $RAW"; exit 0; }
PY=""
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import PIL" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "store_shots: Python with Pillow not found; raw captures only, in $RAW" >&2
  exit 0
fi
case ",$TARGETS," in
  *,ios*|*,ipad*)
    if [ "$CROP_TOP" = 0 ] && [ "$CROP_BOTTOM" = 0 ]; then
      echo "store_shots: WARNING: App Store sizes without --crop-top/--crop-bottom keep the Android bars" >&2
    fi ;;
esac

"$PY" -I - "$RAW" "$OUT" "$TARGETS" "$CROP_TOP" "$CROP_BOTTOM" "$PAD" <<'PYEOF'
import sys
from pathlib import Path
from PIL import Image

raw, out, targets, crop_top, crop_bottom, pad = sys.argv[1:7]
crop_top, crop_bottom = int(crop_top), int(crop_bottom)
bg = tuple(int(pad[i:i + 2], 16) for i in (0, 2, 4))

# Portrait sizes (width, height); landscape captures use them swapped.
SIZES = {
    "play-phone": (1080, 1920),  # Google Play phone, 9:16 (long side at most 2x short)
    "play7": (1200, 1920),       # Google Play 7-inch tablet
    "play10": (1600, 2560),      # Google Play 10-inch tablet
    "ios69": (1320, 2868),       # App Store iPhone 6.9"
    "ios65": (1284, 2778),       # App Store iPhone 6.5"
    "ipad13": (2064, 2752),      # App Store iPad 13"
}

wanted = [t.strip() for t in targets.split(",") if t.strip()]
unknown = [t for t in wanted if t not in SIZES]
if unknown:
    sys.exit(f"store_shots: unknown target(s): {', '.join(unknown)} (known: {', '.join(SIZES)})")

files = sorted(p for p in Path(raw).glob("*.png") if p.is_file())
if not files:
    sys.exit("store_shots: no raw captures to size")

for f in files:
    im = Image.open(f).convert("RGB")  # no alpha: both stores refuse it
    for t in wanted:
        img = im
        if t.startswith(("ios", "ipad")) and (crop_top or crop_bottom):
            w, h = img.size
            if crop_top + crop_bottom < h:
                img = img.crop((0, crop_top, w, h - crop_bottom))
        w, h = img.size
        cw, ch = SIZES[t]
        if w > h:
            cw, ch = ch, cw
        scale = min(cw / w, ch / h)
        nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
        canvas = Image.new("RGB", (cw, ch), bg)
        canvas.paste(img.resize((nw, nh), Image.LANCZOS), ((cw - nw) // 2, (ch - nh) // 2))
        dest = Path(out) / t
        dest.mkdir(parents=True, exist_ok=True)
        canvas.save(dest / f.name, "PNG", optimize=True)
    print(f"sized {f.name}: {', '.join(wanted)}")
PYEOF
