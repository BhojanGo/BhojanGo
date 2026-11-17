#!/bin/sh
# The Maestro flows of the three Expo apps on the Android emulator, against the
# Railway QA environment instead of make dev (dev builds; JS from Metro with the
# QA env profile).
#   RAILWAY_TOKEN=<QA project token> E2E_LOGINS_FILE=/path/outside/the/repo/BhojanGo_QA_Logins.txt \
#   tools/railway/maestro-qa.sh [customer|rider|partner ...]
# Needs: the apps installed on emulator-5554 (make apk APP=...), Maestro, and the
# QA restaurants open (demo seed hours). QA is protected (tools/target_guard.py): only the
# flows tagged qa-readonly run there (below). Passwords go to the
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
# Tests never write to QA or production. Most flows place orders and change data, so
# when tools/target_guard.py refuses the API (QA, exit 3) only the read-only flows run:
# those tagged qa-readonly (they sign in with a seed phone and look; nothing is
# ordered, saved or sent). Production is never a target here.
READONLY=0
if ! python "$ROOT/tools/target_guard.py" api "$QA_CORE" "$QA_RT"; then
  # Read-only flows only where the API itself says it is QA; anything else is refused.
  if ! curl -s -m 10 "$QA_CORE/health" | python -c "import json, sys; sys.exit(0 if str(json.load(sys.stdin).get('environment', '')).lower() == 'qa' else 1)"; then
    sh "$ROOT/tools/mobile/env-profile.sh" local >/dev/null
    exit 3
  fi
  READONLY=1
  echo "QA: read-only flows only (tags: qa-readonly)"
fi
QA_PASSWORDS="$(python -c "
import json, sys
rows = [l.rstrip('\n').split('\t') for l in open(sys.argv[1], encoding='utf-8')]
print(json.dumps({r[2]: r[3] for r in rows if len(r) >= 4 and '@' in r[2]}))" "$E2E_LOGINS_FILE")"
# Admins' authenticator keys (the logins file's fifth column) for their second step.
QA_TOTP_KEYS="$(python -c "
import json, sys
rows = [l.rstrip('\n').split('\t') for l in open(sys.argv[1], encoding='utf-8')]
print(json.dumps({r[2]: r[4] for r in rows if len(r) >= 5 and '@' in r[2] and r[4]}))" "$E2E_LOGINS_FILE")"
timeout 10 adb -s "$DEVICE" shell settings put global hide_error_dialogs 1 >/dev/null 2>&1
sh "$ROOT/tools/mobile/metro-host.sh" "$DEVICE"   # before adb reverse: adb root drops it
adb -s "$DEVICE" reverse tcp:8081 tcp:8081 >/dev/null   # Metro only; the APIs are public URLs
fail=0
for app in $APPS; do
  echo "== $app (Metro with the QA profile)"
  (cd "$ROOT/apps/$app" && CI=1 exec pnpm exec expo start -c --port 8081) > "$OUT/metro-$app.log" 2>&1 &
  METRO=$!
  end=$(( $(date +%s) + 180 ))
  until curl -s -m 3 localhost:8081/status | grep -q running || [ "$(date +%s)" -ge "$end" ]; do sleep 3; done
  # Open the app once so Metro builds the bundle, and close it only once the app has
  # loaded it (tools/mobile/warm-up.sh explains the black first flow this prevents).
  case "$app" in customer) pkg=com.bhojango.app ;; *) pkg="com.bhojango.$app" ;; esac
  sh "$ROOT/tools/mobile/warm-up.sh" "$DEVICE" "$pkg" "$OUT/metro-$app.log" 300
  [ "$app" = rider ] && adb -s "$DEVICE" emu geo fix 78.3925 17.4495 >/dev/null
  # Top-level flows, plus the read-only QA folder (.maestro/qa: every flow there is read-only).
  flows="$(cd "$ROOT/apps/$app/.maestro" && { ls *.yaml; ls qa/*.yaml 2>/dev/null; } | grep -v '^sign-in.yaml$' | sed 's/\.yaml$//')"
  if [ "$READONLY" = 1 ]; then
    flows="$(for f in $flows; do case "$f" in qa/*) echo "$f"; continue;; esac
      grep -Eq '^[[:space:]]*-[[:space:]]*qa-readonly[[:space:]]*$' "$ROOT/apps/$app/.maestro/$f.yaml" && echo "$f"; done)"
  fi
  if [ -n "${ONLY:-}" ]; then  # ONLY="account batch": just these flows (of any app)
    flows="$(for f in $flows; do case " $ONLY " in *" $f "*) echo "$f";; esac; done)"
  fi
  for f in $flows; do
    # PHONE / COUNTRY pick another seed customer (e.g. the Boise demo, +1 208 555 0301,
    # when Hyderabad's demo kitchens are closed at night): passed through when set.
    if maestro --device "$DEVICE" test -e QA_CORE="$QA_CORE" -e QA_RT="$QA_RT" -e QA_PASSWORDS="$QA_PASSWORDS" -e QA_TOTP_KEYS="$QA_TOTP_KEYS"          ${PHONE:+-e PHONE="$PHONE"} ${COUNTRY:+-e COUNTRY="$COUNTRY"} \
         "$ROOT/apps/$app/.maestro/$f.yaml" > "$OUT/$app-$(echo "$f" | tr / -).log" 2>&1; then
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
