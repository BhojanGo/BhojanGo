#!/bin/sh
# Pre-commit: refuse a commit whose staged changes add a JSON Web Token
# (header.payload.signature, both JSON parts base64url, so they start "eyJ").
# Tokens from test runs, logs or k6 summaries must never be committed, even
# expired dev ones. Same pattern as the bhojango-jwt rule in .gitleaks.toml,
# which CI runs over the whole history.
#   sh tools/git-hooks/no-jwt.sh            # what .husky/pre-commit runs
#   sh tools/git-hooks/no-jwt.sh --self-test
# A real false positive: reword it (or split the string); there is no bypass
# list on purpose. `git commit --no-verify` skips it, and CI still catches it.
set -eu
PATTERN='eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}'

if [ "${1:-}" = "--self-test" ]; then
  h=eyJhbGciOiJSUzI1NiJ9; p=eyJzdWIiOiIxMjM0NTY3ODkwIn0
  printf '+token: %s.%s.c2lnbmF0dXJlLXZhbHVl\n' "$h" "$p" | grep -qE "$PATTERN" || { echo "self-test: token not caught" >&2; exit 1; }
  printf '+no token here: eyJhbGciOi only a header\n' | grep -qE "$PATTERN" && { echo "self-test: false positive" >&2; exit 1; }
  echo "no-jwt self-test passed"; exit 0
fi

# Added lines only, in every staged file (binary files are skipped by git).
hits=$(git diff --cached --no-color -U0 --diff-filter=ACMR | awk '
  /^\+\+\+ / { file = substr($0, 7); next }
  /^\+/      { print file ": " substr($0, 2) }' | grep -E "$PATTERN" || true)
if [ -n "$hits" ]; then
  echo "Commit blocked: these staged lines contain a JSON Web Token." >&2
  echo "$hits" | sed -E "s/$PATTERN/<JWT>/g" | cut -c1-200 >&2
  echo "Remove the token (strip it from the test output or summary) and stage again." >&2
  exit 1
fi
