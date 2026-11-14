#!/bin/sh
# Point the Expo apps (customer, rider, partner) at an environment.
#   tools/mobile/env-profile.sh qa      # the Railway QA environment
#   tools/mobile/env-profile.sh local   # make dev on this computer (adb reverse)
# Writes apps/<app>/.env.local (git-ignored; Expo loads it over .env). For qa the
# URLs are read from Railway at run time (railway domain list, with a QA project
# token in RAILWAY_TOKEN), so no environment's URL is written into the code.
# Expo bakes EXPO_PUBLIC_* in when Metro bundles: restart Metro (expo start -c)
# after switching. The worker has no public URL; the apps don't call it.
set -eu
PROFILE="${1:?usage: env-profile.sh <qa|local>}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

domain() {  # the Railway-generated public domain of a service in the token's environment
  railway domain list --service "$1" --json | python -c "
import json, sys
d = json.load(sys.stdin)
items = d if isinstance(d, list) else d.get('domains') or d.get('serviceDomains') or []
names = [x.get('domain') for x in items if isinstance(x, dict) and x.get('domain')]
print(names[0] if names else '')"
}

case "$PROFILE" in
  qa)
    CORE="https://$(domain core-api)"
    REALTIME="https://$(domain realtime)"
    [ "$CORE" != "https://" ] && [ "$REALTIME" != "https://" ] || { echo "no public domain for core-api or realtime" >&2; exit 1; } ;;
  local)
    CORE="http://localhost:8001"
    REALTIME="http://localhost:8004" ;;
  *) echo "unknown profile: $PROFILE (qa | local)" >&2; exit 1 ;;
esac

for app in customer rider partner; do
  cat > "$ROOT/apps/$app/.env.local" <<EOF
# Written by tools/mobile/env-profile.sh $PROFILE. Git-ignored; delete it to go back to .env.
EXPO_PUBLIC_ENV=$PROFILE
EXPO_PUBLIC_CORE_URL=$CORE
EXPO_PUBLIC_REALTIME_URL=$REALTIME
EOF
done
echo "apps now use $PROFILE: core $CORE, realtime $REALTIME (restart Metro with -c)"
