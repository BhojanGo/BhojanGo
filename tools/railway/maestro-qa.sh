#!/bin/sh
# The Maestro flows of the three Expo apps on the Android emulator, against the
# Railway QA environment instead of make dev (dev builds; JS from Metro with the
# QA env profile).
#   RAILWAY_TOKEN=<QA project token> E2E_LOGINS_FILE=/path/outside/the/repo/BhojanGo_QA_Logins.txt \
#   tools/railway/maestro-qa.sh [customer|rider|partner ...]
# Needs: the apps installed on emulator-5554 (make apk APP=...), Maestro, and the
# QA restaurants open (tools/railway/qa-runner.sh job hours). Passwords go to the
# flows' scripts as QA_PASSWORDS (a local maestro argument; never printed).
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEVICE="${DEVICE:-emulator-5554}"
APPS="${*:-customer rider partner}"
OUT="${OUT:-$ROOT/backups/maestro-qa}"
mkdir -p "$OUT"
sh "$ROOT/tools/mobile/env-profile.sh" qa || exit 1
QA_CORE="$(sed -n 's/^EXPO_PUBLIC_CORE_URL=//p' "$ROOT/apps/customer/.env.local")"
QA_RT="$(sed -n 's/^EXPO_PUBLIC_REALTIME_URL=//p' "$ROOT/apps/customer/.env.local")"
QA_PASSWORDS="$(python -c "
import json, sys
rows = [l.rstrip('\n').split('\t') for l in open(sys.argv[1], encoding='utf-8')]
print(json.dumps({r[2]: r[3] for r in rows if len(r) == 4 and '@' in r[2]}))" "$E2E_LOGINS_FILE")"
timeout 10 adb -s "$DEVICE" shell settings put global hide_error_dialogs 1 >/dev/null 2>&1
adb -s "$DEVICE" reverse tcp:8081 tcp:8081 >/dev/null   # Metro only; the APIs are public URLs
fail=0
for app in $APPS; do
  echo "== $app (Metro with the QA profile)"
  (cd "$ROOT/apps/$app" && CI=1 exec pnpm exec expo start -c --port 8081) > "$OUT/metro-$app.log" 2>&1 &
  METRO=$!
  end=$(( $(date +%s) + 180 ))
  until curl -s -m 3 localhost:8081/status | grep -q running || [ "$(date +%s)" -ge "$end" ]; do sleep 3; done
  # Open the app once so Metro builds the bundle it asks for (with a cleared cache the
  # first flow otherwise races the build), then close it again.
  case "$app" in customer) pkg=com.bhojango.app ;; *) pkg="com.bhojango.$app" ;; esac
  adb -s "$DEVICE" shell monkey -p "$pkg" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
  end=$(( $(date +%s) + 240 ))
  until grep -q "Android Bundled" "$OUT/metro-$app.log" || [ "$(date +%s)" -ge "$end" ]; do sleep 3; done
  sleep 10
  adb -s "$DEVICE" shell am force-stop "$pkg" >/dev/null 2>&1
  [ "$app" = rider ] && adb -s "$DEVICE" emu geo fix 78.3925 17.4495 >/dev/null
  flows="$(cd "$ROOT/apps/$app/.maestro" && ls *.yaml | grep -v '^sign-in.yaml$' | sed 's/\.yaml$//')"
  if [ -n "${ONLY:-}" ]; then  # ONLY="account batch": just these flows (of any app)
    flows="$(for f in $flows; do case " $ONLY " in *" $f "*) echo "$f";; esac; done)"
  fi
  for f in $flows; do
    if maestro --device "$DEVICE" test -e QA_CORE="$QA_CORE" -e QA_RT="$QA_RT" -e QA_PASSWORDS="$QA_PASSWORDS" \
         "$ROOT/apps/$app/.maestro/$f.yaml" > "$OUT/$app-$f.log" 2>&1; then
      echo "PASS $app/$f"
    else
      echo "FAIL $app/$f (see $OUT/$app-$f.log)"; fail=1
    fi
  done
  kill "$METRO" 2>/dev/null; wait "$METRO" 2>/dev/null
  # expo start leaves node children: free the port for the next app
  for pid in $(netstat -ano 2>/dev/null | awk '/:8081 .*LISTENING/ {print $NF}' | sort -u); do taskkill //PID "$pid" //F >/dev/null 2>&1; done
done
sh "$ROOT/tools/mobile/env-profile.sh" local >/dev/null
# Maestro writes every -e value into its run logs: take the passwords out again.
python "$ROOT/tools/railway/redact_logins.py" "$E2E_LOGINS_FILE" "$HOME/.maestro/tests" "$OUT"
exit $fail
