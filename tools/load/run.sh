#!/bin/sh
# P24: run the k6 load test (tools/load/pilot.js) against `make dev`.
#   tools/load/run.sh            # 5 minutes at 10× pilot peak
#   DURATION=1m tools/load/run.sh
# k6 runs in Docker on the compose network. Hyderabad is opened around the
# clock for the run (tools/mobile/hours.py) and the results go to
# tools/load/out/summary.json.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-bhojango}" MSYS_NO_PATHCONV=1
mkdir -p "$ROOT/tools/load/out"
python "$ROOT/tools/mobile/hours.py" open >/dev/null
docker run --rm --network "${COMPOSE_PROJECT_NAME}_default" -e DURATION="${DURATION:-5m}" -e ONLY="${ONLY:-}" \
  -v "$ROOT/tools/load:/scripts" grafana/k6:0.57.0 \
  run --summary-export /scripts/out/summary.json --summary-trend-stats "avg,p(50),p(90),p(95),p(99),max" /scripts/pilot.js
status=$?
python "$ROOT/tools/mobile/hours.py" close >/dev/null
exit $status
