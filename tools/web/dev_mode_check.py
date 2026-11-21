"""The website and admin are never served by `next dev` on QA or production (R24). Stdlib only.

R23's sign-in screenshots showed Next.js's "N" dev indicator. They came from a local `next dev`,
and QA runs `next build` + `next start` (infra/docker/next-app.Dockerfile). This keeps it that way:

    python tools/web/dev_mode_check.py --source         # the image builds and starts production Next.js
    python tools/web/dev_mode_check.py --qa             # QA's website and admin pages are production builds
    python tools/web/dev_mode_check.py URL [URL ...]    # any pages (production after go-live)

A page from `next dev` loads the dev tools and React's development build; a production build
loads only hashed chunks. Markers taken from a real `next dev` page (Next 16, Turbopack) and
the webpack dev server's. Exit 1 on any dev page, a page that doesn't answer, or a source problem.
"""
from __future__ import annotations

import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QA_URLS = ["https://qa.bhojango.com/", "https://qa.bhojango.com/signin", "https://admin.qa.bhojango.com/login"]

DEV_MARKERS = {
    "next-devtools": re.compile(r"next[-_]dist[-_]compiled[-_]next-devtools|next-devtools"),
    "React development build": re.compile(r"_next/static/chunks/[^\"'\s]*react-dom[^\"'\s]*_development_"),
    "Turbopack dev chunks": re.compile(r"(?:%5B|\[)root-of-the-server(?:%5D|\])"),
    "hot reload": re.compile(r"webpack-hmr|hmr-client|react-refresh"),
}


def dev_markers(html: str) -> list[str]:
    """The dev-mode markers found in a page (empty for a production build)."""
    return [name for name, rx in DEV_MARKERS.items() if rx.search(html)]


def source_problems(dockerfile: str, railway_ts: str) -> list[str]:
    """What would let a hosted image run `next dev`."""
    problems = []
    cmd = [ln for ln in dockerfile.splitlines() if ln.strip().startswith("CMD")]
    if not cmd or "next start" not in cmd[-1]:
        problems.append("next-app.Dockerfile: the last CMD doesn't run `next start`")
    if not re.search(r"^RUN .*\bturbo build\b", dockerfile, re.M):
        problems.append("next-app.Dockerfile: no `turbo build` (next build) step")
    if not re.search(r"^ENV .*\bNODE_ENV=production\b", dockerfile, re.M):
        problems.append("next-app.Dockerfile: the run stage doesn't set NODE_ENV=production")
    for name, text in (("next-app.Dockerfile", dockerfile), (".railway/railway.ts", railway_ts)):
        if re.search(r"\bnext\s+dev\b|\bpnpm\s+(?:run\s+)?dev\b|startCommand", text):
            problems.append(f"{name}: mentions a dev server or a start command override")
    return problems


def check_url(url: str) -> str | None:
    req = urllib.request.Request(url, headers={"User-Agent": "bhojango-dev-mode-check"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            html = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        html = e.read().decode("utf-8", "replace")  # a 404 page is still a page of the same build
    except (urllib.error.URLError, TimeoutError) as e:
        return f"{url}: no answer ({e})"
    if "_next/static/" not in html:
        return f"{url}: not a Next.js page"
    found = dev_markers(html)
    return f"{url}: served by `next dev` ({', '.join(found)})" if found else None


def main(argv: list[str]) -> int:
    if argv == ["--source"]:
        problems = source_problems((ROOT / "infra/docker/next-app.Dockerfile").read_text(encoding="utf-8"),
                                   (ROOT / ".railway/railway.ts").read_text(encoding="utf-8"))
        for p in problems:
            print("FAIL", p)
        print("source: production Next.js only" if not problems else f"{len(problems)} problem(s)")
        return 1 if problems else 0
    urls = QA_URLS if argv == ["--qa"] else argv
    if not urls:
        print(__doc__)
        return 2
    bad = [p for p in (check_url(u) for u in urls) if p]
    for u in urls:
        print("FAIL" if any(b.startswith(u + ":") for b in bad) else "ok  ", u)
    for b in bad:
        print("FAIL", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
