#!/bin/sh
# Run an app's Maestro flows on the Android emulator against `make dev`.
#   tools/mobile/e2e.sh customer [flow ...]
# Needs: the app installed (make apk APP=...; adb -s emulator-5554 install -r),
# Metro running for it, adb reverse for 8081/8001/8004/8006, Maestro installed.
# Each flow starts from a clean sign-in, so OTP send counters are reset first;
# Hyderabad is opened around the clock for the run and restored afterwards.
set -u
APP="${1:?usage: e2e.sh <customer|rider|partner> [flow ...]}"
shift
ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"  # a Windows path under Git Bash (MSYS_NO_PATHCONV below)
DEVICE="${DEVICE:-emulator-5554}"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-bhojango}" MSYS_NO_PATHCONV=1
COMPOSE="docker compose -f $ROOT/infra/docker/compose.yaml"
# sign-in.yaml is a sub-flow the others start with.
FLOWS="${*:-$(cd "$ROOT/apps/$APP/.maestro" && ls *.yaml | grep -v '^sign-in.yaml$' | sed 's/\.yaml$//')}"

python "$ROOT/tools/mobile/hours.py" open >/dev/null
if [ "$APP" = rider ]; then
  # The rider waits near Spice Route Kitchen, Madhapur (emulator GPS: longitude latitude).
  adb -s "$DEVICE" emu geo fix 78.3925 17.4495 >/dev/null
fi
fail=0
# A busy host can leave an "isn't responding" dialog over everything (often System UI):
# answer "Wait" before each flow so it doesn't hide the app.
dismiss_anr() {
  if timeout 10 adb -s "$DEVICE" shell dumpsys window 2>/dev/null | grep -q "mCurrentFocus=.*Application Not Responding"; then
    echo "dismissing an 'isn't responding' dialog"
    timeout 10 adb -s "$DEVICE" shell input keyevent KEYCODE_BACK >/dev/null 2>&1
    sleep 2
  fi
}
for f in $FLOWS; do
  dismiss_anr
  $COMPOSE exec -T redis sh -c "redis-cli -n 0 --scan --pattern 'otp_attempts:*' | xargs -r redis-cli -n 0 del" >/dev/null
  if maestro --device "$DEVICE" test "$ROOT/apps/$APP/.maestro/$f.yaml" >/tmp/maestro-$f.log 2>&1; then
    echo "PASS $f"
  else
    echo "FAIL $f (see /tmp/maestro-$f.log)"; fail=1
  fi
done
python "$ROOT/tools/mobile/hours.py" close >/dev/null
# Screenshots the flows took (Maestro writes them under ~/.maestro/tests/<run>/).
mkdir -p "$ROOT/docs/screenshots/$APP"
for d in $(ls -td "$HOME"/.maestro/tests/* 2>/dev/null | head -20 | tac); do
  cp -f "$d"/*/takeScreenshot/docs/screenshots/"$APP"/*.png "$ROOT/docs/screenshots/$APP/" 2>/dev/null
done
exit $fail
