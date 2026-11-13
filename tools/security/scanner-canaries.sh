#!/bin/sh
# Prove the scanners work: plant fake findings and require each scanner to catch them.
# A scan with no findings proves nothing until it has caught one (PLAYBOOK rule 34).
#   tools/security/scanner-canaries.sh gitleaks   # our .gitleaks.toml: a JWT (our rule) and an AWS key (a default rule)
#   tools/security/scanner-canaries.sh semgrep    # the rulesets CI uses: pickle.loads, shell=True
# The fake secrets are built at run time, in a git-ignored folder, so they never reach git.
# (The access-control sweep's canaries are tests in core_api/integration/test_zz_access_sweep.py.)
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
export MSYS_NO_PATHCONV=1
DIR="$ROOT/backups/scanner-canary-$1"
rm -rf "$DIR"; mkdir -p "$DIR"
trap 'rm -rf "$DIR"' EXIT
fail() { echo "CANARY NOT CAUGHT ($1): $2" >&2; exit 1; }

case "$1" in
gitleaks)
  b64() { printf '%s' "$1" | base64 | tr '+/' '-_' | tr -d '=\n'; }
  jwt="$(b64 '{"alg":"RS256","typ":"JWT"}').$(b64 '{"sub":"canary","exp":1700000000}').c2lnbmF0dXJlLWNhbmFyeS0xMjM0NTY3ODk"
  printf 'token = "%s"\n' "$jwt" > "$DIR/leak.py"
  printf 'aws_access_key_id = %s\n' "AKIA$(printf 'Q3EGRV4TZ7XB2KMN')" > "$DIR/settings.ini"
  set +e
  docker run --rm -v "$DIR:/scan" -v "$ROOT/.gitleaks.toml:/cfg/gitleaks.toml:ro" zricethezav/gitleaks:v8.21.2 \
    dir /scan --config /cfg/gitleaks.toml --redact --no-banner --report-format json --report-path /scan/report.json >/dev/null 2>&1
  code=$?
  set -e
  [ "$code" -ne 0 ] || fail gitleaks "exited 0 on planted secrets"
  for rule in bhojango-jwt aws-access-token; do
    grep -q "\"RuleID\": \"$rule\"" "$DIR/report.json" || fail gitleaks "rule $rule found nothing"
  done
  echo "gitleaks canaries caught: bhojango-jwt, aws-access-token"
  ;;
semgrep)
  cat > "$DIR/canary.py" <<'PY'
import pickle
import subprocess


def handler(blob: bytes, name: str) -> object:
    subprocess.call("convert " + name, shell=True)
    return pickle.loads(blob)
PY
  CONFIGS="${SEMGREP_CONFIGS:---config p/python --config p/security-audit}"
  docker run --rm -v "$DIR:/src" -w /src semgrep/semgrep:1.113.0 \
    semgrep scan $CONFIGS --json --quiet --metrics=off -o /src/report.json /src >/dev/null 2>&1 || true
  [ -s "$DIR/report.json" ] || fail semgrep "no report"
  for hit in pickle shell; do
    grep -o '"check_id": *"[^"]*"' "$DIR/report.json" | grep -qi "$hit" || fail semgrep "nothing about $hit"
  done
  echo "semgrep canaries caught: $(grep -o '"check_id": *"[^"]*"' "$DIR/report.json" | sed 's/.*\.//; s/"//' | sort -u | tr '\n' ' ')"
  ;;
*) echo "usage: $0 gitleaks|semgrep" >&2; exit 2 ;;
esac
