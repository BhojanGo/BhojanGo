#!/bin/sh
# gitleaks over the working tree: every file git would commit (tracked, plus
# untracked files that aren't ignored), as they are on disk now. Run it before
# every commit that touches deploy config. `make ci-secrets` scans the history.
#   tools/security/gitleaks-tree.sh
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cd "$ROOT"
git ls-files -z --cached --others --exclude-standard -- . ':!Claude outputs' \
  | xargs -0 -I{} sh -c '[ -f "$1" ] && mkdir -p "$2/$(dirname "$1")" && cp "$1" "$2/$1" || true' _ {} "$TMP/tree"
echo "scanning $(find "$TMP/tree" -type f | wc -l | tr -d ' ') files"
MSYS_NO_PATHCONV=1 docker run --rm -v "$(cd "$TMP" && (pwd -W 2>/dev/null || pwd))/tree:/scan:ro" \
  -v "$(pwd -W 2>/dev/null || pwd)/.gitleaks.toml:/cfg/gitleaks.toml:ro" \
  -v "$(pwd -W 2>/dev/null || pwd)/.gitleaksignore:/cfg/.gitleaksignore:ro" \
  zricethezav/gitleaks:v8.21.2 dir /scan --config /cfg/gitleaks.toml --gitleaks-ignore-path /cfg/.gitleaksignore --redact --no-banner
