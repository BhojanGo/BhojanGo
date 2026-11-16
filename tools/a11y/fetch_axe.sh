#!/bin/sh
# Puts axe-core's axe.min.js in tools/a11y/vendor/ for the e2e runs (mounted at /a11y).
# The version is the one pinned in the root package.json (devDependencies, exact). From
# node_modules when `pnpm install` has run; otherwise (the GitHub runner) `npm pack` of
# that exact version from the npm registry, checked against the lockfile's integrity.
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEST="$ROOT/tools/a11y/vendor"
VERSION="$(sed -n 's/.*"axe-core": *"\([0-9.]*\)".*/\1/p' "$ROOT/package.json")"
[ -n "$VERSION" ] || { echo "axe-core is not pinned in package.json" >&2; exit 1; }
mkdir -p "$DEST"
if [ -f "$DEST/axe.min.js" ] && grep -q "axe v$VERSION" "$DEST/axe.min.js"; then exit 0; fi
if [ -f "$ROOT/node_modules/axe-core/axe.min.js" ] && grep -q "axe v$VERSION" "$ROOT/node_modules/axe-core/axe.min.js"; then
  cp "$ROOT/node_modules/axe-core/axe.min.js" "$DEST/axe.min.js"
  exit 0
fi
TMP="$(mktemp -d)"
( cd "$TMP" && npm pack --silent "axe-core@$VERSION" >/dev/null )
WANT="$(sed -n "/^  axe-core@$VERSION:/,/integrity/s/.*integrity: *\(sha512-[^,} ]*\).*/\1/p" "$ROOT/pnpm-lock.yaml" | head -1)"
GOT="sha512-$(openssl dgst -sha512 -binary "$TMP/axe-core-$VERSION.tgz" | openssl base64 -A)"
[ -z "$WANT" ] || [ "$WANT" = "$GOT" ] || { echo "axe-core $VERSION: integrity mismatch" >&2; exit 1; }
tar -xzf "$TMP/axe-core-$VERSION.tgz" -C "$TMP" package/axe.min.js
cp "$TMP/package/axe.min.js" "$DEST/axe.min.js"
rm -rf "$TMP"
