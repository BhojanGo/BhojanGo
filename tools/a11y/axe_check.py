"""Accessibility checks (axe-core) for the Playwright end-to-end runs (R9 item 7).

Used by tools/web/e2e_web.py and tools/admin/e2e_admin.py:

    from axe_check import Axe
    axe = Axe("web")
    check("a11y landing: no serious or critical issues", lambda: axe.scan(page, "landing"))
    ...
    axe.write(OUT)   # a11y-web.json + a11y-web.md: every violation, every impact

`scan` runs axe-core on the page as it is (WCAG 2.0/2.1/2.2 A and AA plus axe's
best practices) and raises when a serious or critical violation is found that is
not in EXCEPTIONS, so the run fails. Everything else (moderate, minor) is only
reported, for the lead to schedule.

axe-core is pinned in the root package.json (devDependency, exact version). The
e2e scripts copy node_modules/axe-core/axe.min.js to tools/a11y/vendor/ (or fetch
that exact version with `npm pack` when node_modules isn't installed, as on the
GitHub runner) and mount this folder at /a11y in the Playwright image.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
_CANDIDATES = [
    os.environ.get("AXE_JS", ""),
    "/a11y/vendor/axe.min.js",
    str(HERE / "vendor" / "axe.min.js"),
    str(HERE.parent.parent / "node_modules" / "axe-core" / "axe.min.js"),
]

TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"]
BLOCKING = ("serious", "critical")

# Narrow, documented exceptions: (page name or "*", axe rule id) -> why it can't be
# fixed now. Nothing is allowed silently: an exception still shows in the report.
# Empty: every serious or critical finding on the scanned pages was fixed in R9.
EXCEPTIONS: dict[tuple[str, str], str] = {}


def _axe_js() -> str:
    for p in _CANDIDATES:
        if p and os.path.isfile(p):
            return p
    raise FileNotFoundError("axe.min.js not found: run `pnpm install` or let e2e.sh fetch it (tools/a11y/vendor/)")


class Axe:
    def __init__(self, suite: str) -> None:
        self.suite = suite
        self.pages: dict[str, list[dict]] = {}
        self.js = _axe_js()

    def run(self, page, name: str) -> list[dict]:  # type: ignore[no-untyped-def]
        """Runs axe on the page and records every violation under `name`."""
        if not page.evaluate("() => typeof window.axe !== 'undefined'"):
            page.add_script_tag(path=self.js)
        raw = page.evaluate(
            """async (tags) => {
                const r = await window.axe.run({ exclude: [['nextjs-portal']] }, { runOnly: { type: 'tag', values: tags }, resultTypes: ['violations'] });
                return r.violations.map((v) => ({
                    id: v.id, impact: v.impact, help: v.help, helpUrl: v.helpUrl, tags: v.tags,
                    nodes: v.nodes.slice(0, 8).map((n) => ({ target: n.target.join(' '), html: n.html.slice(0, 240), summary: (n.failureSummary || '').slice(0, 400) })),
                    count: v.nodes.length,
                }));
            }""",
            TAGS,
        )
        for v in raw:
            v["page"] = name
            v["url"] = page.url
            reason = EXCEPTIONS.get((name, v["id"])) or EXCEPTIONS.get(("*", v["id"]))
            if reason:
                v["exception"] = reason
        self.pages[name] = raw
        return raw

    def scan(self, page, name: str) -> None:  # type: ignore[no-untyped-def]
        """Runs axe and raises on any serious or critical violation not in EXCEPTIONS."""
        bad = [v for v in self.run(page, name) if v["impact"] in BLOCKING and "exception" not in v]
        if bad:
            raise AssertionError("; ".join(
                f"{v['impact']} {v['id']} x{v['count']} ({v['nodes'][0]['target'] if v['nodes'] else ''})" for v in bad))

    def counts(self) -> dict[str, int]:
        c = {"critical": 0, "serious": 0, "moderate": 0, "minor": 0}
        for vs in self.pages.values():
            for v in vs:
                c[v["impact"] or "minor"] = c.get(v["impact"] or "minor", 0) + 1
        return c

    def write(self, out_dir: str) -> None:
        """a11y-<suite>.json (everything) and a11y-<suite>.md (a table to read)."""
        os.makedirs(out_dir, exist_ok=True)
        data = {"suite": self.suite, "tags": TAGS, "counts": self.counts(), "pages": self.pages}
        Path(out_dir, f"a11y-{self.suite}.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
        lines = [f"# Accessibility (axe-core) · {self.suite}", "",
                 "Counts are rules violated per page (each may hit several elements).", "",
                 "| Impact | Rules violated |", "|---|---|"]
        lines += [f"| {k} | {v} |" for k, v in data["counts"].items()]
        lines += ["", "| Page | Impact | Rule | Elements | What | Exception |", "|---|---|---|---|---|---|"]
        order = {"critical": 0, "serious": 1, "moderate": 2, "minor": 3}
        for name, vs in self.pages.items():
            if not vs:
                lines.append(f"| {name} | none | | | | |")
            for v in sorted(vs, key=lambda x: order.get(x["impact"] or "minor", 4)):
                where = v["nodes"][0]["target"] if v["nodes"] else ""
                lines.append(f"| {name} | {v['impact']} | [{v['id']}]({v['helpUrl']}) | {v['count']} | {v['help']} (`{where[:80]}`) | {v.get('exception', '')} |")
        Path(out_dir, f"a11y-{self.suite}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"a11y {self.suite}: {data['counts']} -> {out_dir}/a11y-{self.suite}.md", flush=True)
