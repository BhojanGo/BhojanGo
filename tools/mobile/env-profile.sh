#!/bin/sh
# Point the Expo apps (customer, rider, partner) at an environment.
#   tools/mobile/env-profile.sh qa      # the Railway QA environment
#   tools/mobile/env-profile.sh local   # make dev on this computer (adb reverse)
# Writes apps/<app>/.env.local (git-ignored; Expo loads it over .env). QA has its own
# addresses on bhojango.com since 2026-11-19 (api.qa, rt.qa, qa: Railway custom domains),
# the same ones the apps' eas.json preview profile uses.
# Expo bakes EXPO_PUBLIC_* in when Metro bundles: restart Metro (expo start -c)
# after switching. The worker has no public URL; the apps don't call it.
# EXPO_PUBLIC_APP_ENV (qa | local) puts the test-site banner on every screen; a
# store build sets production and shows none (packages/mobile-core/src/env.ts).
set -eu
PROFILE="${1:?usage: env-profile.sh <qa|local>}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

case "$PROFILE" in
  qa)
    CORE="https://api.qa.bhojango.com"
    REALTIME="https://rt.qa.bhojango.com"
    WEB="https://qa.bhojango.com" ;;
  local)
    CORE="http://localhost:8001"
    REALTIME="http://localhost:8004"
    WEB="http://localhost:3000" ;;
  *) echo "unknown profile: $PROFILE (qa | local)" >&2; exit 1 ;;
esac

for app in customer rider partner; do
  cat > "$ROOT/apps/$app/.env.local" <<EOF
# Written by tools/mobile/env-profile.sh $PROFILE. Git-ignored; delete it to go back to .env.
EXPO_PUBLIC_APP_ENV=$PROFILE
EXPO_PUBLIC_ENV=$PROFILE
EXPO_PUBLIC_CORE_URL=$CORE
EXPO_PUBLIC_REALTIME_URL=$REALTIME
EXPO_PUBLIC_WEB_URL=$WEB
EOF
done
echo "apps now use $PROFILE: core $CORE, realtime $REALTIME, web ${WEB:-none} (restart Metro with -c)"
