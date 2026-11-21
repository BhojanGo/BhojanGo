"""Tests for tools/web/dev_mode_check.py (R24): it fails on a `next dev` page and on an image that
could run one, and passes on a production page and on the repo's Dockerfile. Run: python tools/web/dev_mode_check_test.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dev_mode_check import ROOT, dev_markers, source_problems  # noqa: E402

# Script tags from a real `next dev -p 3999` page of apps/web (Next 16, Turbopack, 2026-11-20).
DEV_PAGE = """<html><head>
<link rel="stylesheet" href="/_next/static/chunks/%5Broot-of-the-server%5D__1cag343pndzq7._.css"/>
<script src="/_next/static/chunks/1daa_next_dist_compiled_react-dom_cjs_react-dom-client_development_0mp0cp_t-ezj9.js" async=""></script>
<script src="/_next/static/chunks/node_modules_next_dist_compiled_react-server-dom-turbopack_164kp-67asdr9._.js" async=""></script>
<script src="/_next/static/chunks/node_modules_next_dist_compiled_next-devtools_index_090k2jmam7qwg.js" async=""></script>
</head></html>"""
# The same tags from QA's production build (qa.bhojango.com/terms, the same day).
PROD_PAGE = """<html><head>
<link rel="stylesheet" href="/_next/static/chunks/3nu28guu3cidf.css"/>
<script src="/_next/static/chunks/1d-3ziz_810o8.js" async=""></script>
<script src="/_next/static/chunks/29u-0qotb-oos.js" async=""></script>
<p>Our development team builds the menus.</p>
</head></html>"""
# The webpack dev server's tell-tales (next dev --webpack).
WEBPACK_DEV = '<script src="/_next/static/chunks/webpack.js"></script><script>new EventSource("/_next/webpack-hmr")</script>'

failures = 0


def check(name: str, ok: bool) -> None:
    global failures
    print(("ok   " if ok else "FAIL ") + name)
    failures += 0 if ok else 1


found = dev_markers(DEV_PAGE)
check("a next dev page is caught", bool(found))
check("by next-devtools, the React development build and Turbopack dev chunks",
      {"next-devtools", "React development build", "Turbopack dev chunks"} <= set(found))
check("a webpack dev page is caught", dev_markers(WEBPACK_DEV) == ["hot reload"])
check("a production page passes (the word 'development' in text is fine)", dev_markers(PROD_PAGE) == [])

dockerfile = (ROOT / "infra/docker/next-app.Dockerfile").read_text(encoding="utf-8")
railway = (ROOT / ".railway/railway.ts").read_text(encoding="utf-8")
check("the repo's image and Railway config pass", source_problems(dockerfile, railway) == [])
dev_cmd = dockerfile.replace("next start", "next dev")
check("an image that starts `next dev` fails", any("next start" in p for p in source_problems(dev_cmd, railway)))
check("an image without NODE_ENV=production fails",
      any("NODE_ENV" in p for p in source_problems(dockerfile.replace("NODE_ENV=production", "NODE_ENV=development"), railway)))
check("a Railway start command override fails",
      any("railway.ts" in p for p in source_problems(dockerfile, railway + '\nstartCommand: "pnpm dev"')))

print(f"{failures} failure(s)" if failures else "all passed")
sys.exit(1 if failures else 0)
