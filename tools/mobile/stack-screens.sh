#!/bin/bash
# The app states QA can't show (they write data): Maestro flows under
# apps/<app>/.maestro/stack/ on an Android emulator, against a throwaway local stack.
# Runs on GitHub Actions (.github/workflows/app-screens.yml), never against QA.
#   tools/mobile/stack-screens.sh <device: phone|tablet> <app> [app ...]
#   FLOWS="01-onboarding-new 02-onboarding-seed" REPEAT=20 ...  only those flows, in that order, N times (R21)
# Needs: the stack on localhost (core 8001, realtime 8004), the APKs in .apk/,
# Maestro on PATH, emulator-5554 booted. Screenshots go to $OUT/<app>-<device>/.
set -u
DEVICE_KIND="${1:?usage: stack-screens.sh <phone|tablet> <app> [app ...]}"
shift
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEVICE="${DEVICE:-emulator-5554}"
OUT="${OUT:-$ROOT/stack-screens-out}"
LOGS="$OUT/logs"
mkdir -p "$LOGS"
COMPOSE="docker compose -f $ROOT/infra/docker/compose.yaml"

# Tests never write to QA or production: the stack must be this machine's.
python3 "$ROOT/tools/target_guard.py" api http://localhost:8001 http://localhost:8004 || exit 3

FLOWS="${FLOWS:-}"
REPEAT="${REPEAT:-1}"
# R21: a device log big enough to hold a whole flow, kept in full when a flow fails.
adb -s "$DEVICE" logcat -G 16M >/dev/null 2>&1
adb -s "$DEVICE" shell settings put global hide_error_dialogs 1 >/dev/null 2>&1
adb -s "$DEVICE" shell settings put global window_animation_scale 0 >/dev/null 2>&1
adb -s "$DEVICE" shell settings put global transition_animation_scale 0 >/dev/null 2>&1
adb -s "$DEVICE" shell settings put global animator_duration_scale 0 >/dev/null 2>&1
# The phone reaches Metro and the stack through adb reverse (localhost on the phone).
# 8011 is tools/mobile/slow_proxy.py in front of core (the customer app's loading state).
sh "$ROOT/tools/mobile/metro-host.sh" "$DEVICE"   # before adb reverse: adb root drops it
for p in 8081 8001 8004 8006 8011; do adb -s "$DEVICE" reverse tcp:$p tcp:$p >/dev/null; done

python3 "$ROOT/tools/mobile/slow_proxy.py" 8011 http://localhost:8001 > "$LOGS/proxy.log" 2>&1 &
PROXY=$!
trap 'kill $PROXY 2>/dev/null' EXIT

fail=0
for app in "$@"; do
  case "$app" in customer) pkg=com.bhojango.app ;; *) pkg="com.bhojango.$app" ;; esac
  adb -s "$DEVICE" install -r "$ROOT/.apk/$app-debug.apk" > "$LOGS/install-$app.log" 2>&1 || { echo "install $app failed"; cat "$LOGS/install-$app.log"; fail=1; continue; }
  core=http://localhost:8001
  [ "$app" = customer ] && core=http://localhost:8011
  cat > "$ROOT/apps/$app/.env.local" <<EOF
EXPO_PUBLIC_APP_ENV=local
EXPO_PUBLIC_ENV=local
EXPO_PUBLIC_CORE_URL=$core
EXPO_PUBLIC_REALTIME_URL=http://localhost:8004
EXPO_PUBLIC_WEB_URL=
EOF
  echo "== $app: Metro"
  (cd "$ROOT/apps/$app" && CI=1 exec pnpm exec expo start -c --port 8081) > "$LOGS/metro-$app.log" 2>&1 &
  METRO=$!
  end=$(( $(date +%s) + 240 ))
  until curl -s -m 3 localhost:8081/status | grep -q running || [ "$(date +%s)" -ge "$end" ]; do sleep 3; done
  # Open the app once so Metro builds the bundle before the first flow (a cold build is
  # slow), and close it only once the app has loaded it (see tools/mobile/warm-up.sh).
  sh "$ROOT/tools/mobile/warm-up.sh" "$DEVICE" "$pkg" "$LOGS/metro-$app.log" 600
  # The phone waits in Madhapur (geo fix: longitude latitude); customers use saved addresses.
  adb -s "$DEVICE" emu geo fix 78.3925 17.4495 >/dev/null
  if [ -n "$FLOWS" ]; then list=""; for f in $FLOWS; do [ -f "$ROOT/apps/$app/.maestro/stack/$f.yaml" ] && list="$list $f.yaml"; done
  else list="$(cd "$ROOT/apps/$app/.maestro/stack" && ls *.yaml)"; fi
  for run in $(seq 1 "$REPEAT"); do
  for flow in $list; do
    # Every flow starts with a fresh sign-in: reset the OTP send counters.
    $COMPOSE exec -T redis sh -c "redis-cli -n 0 --scan --pattern 'otp_*' | xargs -r redis-cli -n 0 del" >/dev/null 2>&1
    name="$app-${flow%.yaml}"
    [ "$REPEAT" -gt 1 ] && name="$name-run$run"
    # R18: a flow that needs an incident pause on the stack (tools/mobile/incident_pause.py on/off around it).
    pause=0
    case "$flow" in *incident-pause*) pause=1; python3 "$ROOT/tools/mobile/incident_pause.py" on > "$LOGS/$name-pause.log" 2>&1 ;; esac
    # R20: the app's own console warnings and errors (LogBox only says "Open debugger to view
    # warnings"; the JS console also goes to logcat as ReactNativeJS), one file per flow.
    adb -s "$DEVICE" logcat -c >/dev/null 2>&1
    # R21: is the previous flow's Maestro driver still on the phone as this flow's starts?
    echo "$name start: driver $(adb -s "$DEVICE" shell pidof dev.mobile.maestro 2>/dev/null | tr -d '\r' || true)" >> "$LOGS/driver.txt"
    if (cd "$OUT" && timeout 600 maestro --device "$DEVICE" test "$ROOT/apps/$app/.maestro/stack/$flow") > "$LOGS/$name.log" 2>&1; then
      echo "PASS $name"; echo "${name%-run*} PASS" >> "$LOGS/tally.txt"
    else
      echo "FAIL $name"; tail -30 "$LOGS/$name.log"; fail=1; echo "${name%-run*} FAIL" >> "$LOGS/tally.txt"
      # R21: the whole device log of this flow (the Maestro driver's start, the system's kills).
      adb -s "$DEVICE" logcat -d -v threadtime > "$LOGS/$name-logcat.log" 2>/dev/null
      { adb -s "$DEVICE" forward --list; adb -s "$DEVICE" shell ps -A -o PID,NAME | grep -iE "maestro|bhojango"; } > "$LOGS/$name-device.txt" 2>&1
      adb -s "$DEVICE" exec-out screencap -p > "$LOGS/$name-failed.png" 2>/dev/null
      # Maestro's own debug output (screenshot at the failure, view hierarchy).
      last="$(ls -td "$HOME"/.maestro/tests/*/ 2>/dev/null | head -1)"
      [ -n "$last" ] && cp -r "$last" "$LOGS/$name-maestro" 2>/dev/null
    fi
    echo "$name end: driver $(adb -s "$DEVICE" shell pidof dev.mobile.maestro 2>/dev/null | tr -d '\r' || true)" >> "$LOGS/driver.txt"
    # BACK_TO_BACK=1 (flake hunting): the next flow starts at once, nothing in between.
    [ "${BACK_TO_BACK:-0}" = 1 ] && continue
    adb -s "$DEVICE" logcat -d -v brief ReactNativeJS:W '*:S' > "$LOGS/$name-js-warnings.log" 2>/dev/null
    n=$(grep -c '^[WE]/ReactNativeJS' "$LOGS/$name-js-warnings.log" 2>/dev/null); echo "   $name: ${n:-0} JS warnings/errors (logs/$name-js-warnings.log)"
    curl -s -m 5 localhost:8011/__slow/off >/dev/null
    [ "$pause" = 1 ] && python3 "$ROOT/tools/mobile/incident_pause.py" off >> "$LOGS/$name-pause.log" 2>&1
  done
  done
  kill "$METRO" 2>/dev/null; wait "$METRO" 2>/dev/null
  pkill -f "expo start" 2>/dev/null; pkill -f "metro" 2>/dev/null; sleep 3
done

# Maestro writes takeScreenshot files into its run folders (~/.maestro/tests/...) or the
# working directory, depending on the version: gather stack-<app>-<shot>.png from both.
for f in $(find "$HOME/.maestro" "$OUT" -name 'stack-*.png' -not -path "$OUT/*-*/*" 2>/dev/null); do
  b="$(basename "$f" .png)"; app="$(echo "$b" | cut -d- -f2)"; shot="${b#stack-"$app"-}"
  mkdir -p "$OUT/$app-$DEVICE_KIND"
  cp -f "$f" "$OUT/$app-$DEVICE_KIND/stack-$shot.png"  # the names tools/mobile/screens_compose.py pairs
done
# Every distinct JS warning and error the flows hit (first line of each), most frequent first.
echo "== JS warnings and errors (ReactNativeJS in logcat)"
cat "$LOGS"/*-js-warnings.log 2>/dev/null | grep '^[WE]/ReactNativeJS' | sed 's/([ 0-9]*)//' | sort | uniq -c | sort -rn | head -40
if [ "$REPEAT" -gt 1 ] && [ -f "$LOGS/tally.txt" ]; then
  echo "== Repeat tally (passed of runs)"
  sort "$LOGS/tally.txt" | uniq -c | awk '{print "  " $2 " " $3 ": " $1}'
  echo "== Was the last flow's Maestro driver still running when the next flow started? (logs/driver.txt)"
  grep -c ' start: driver [0-9]' "$LOGS/driver.txt" | sed 's/^/  flows that started with the old driver still running: /'
fi
ls -R "$OUT" | grep -v '^$'
exit $fail
