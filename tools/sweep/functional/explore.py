"""R42: what each website and admin page offers, for writing its functional spec: buttons, links, inputs, selects,
toggles, test ids, and the amounts, counts and dates it shows. One JSON per run (OUT/explore.json).

Runs like tools/sweep/sweep_web.py (Playwright image on the stack's network; a test database only).
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
import sweep_web as sw  # noqa: E402  (refuses anything but a local test stack)
from playwright.sync_api import sync_playwright  # noqa: E402

INVENTORY_JS = """() => {
  const vis = el => { const s = getComputedStyle(el); return s.display !== 'none' && s.visibility !== 'hidden' && el.getClientRects().length; };
  const name = el => (el.getAttribute('aria-label') || el.innerText || el.value || el.title || '').trim().replace(/\\s+/g, ' ').slice(0, 60);
  const label = el => { if (el.id) { const l = document.querySelector(`label[for="${el.id}"]`); if (l) return l.innerText.trim(); }
    return (el.getAttribute('aria-label') || el.placeholder || el.name || el.closest('label')?.innerText || '').trim().slice(0, 60); };
  const out = {buttons: [], links: [], inputs: [], selects: [], toggles: [], testids: []};
  for (const b of document.querySelectorAll('button, [role=button], input[type=submit]')) if (vis(b)) out.buttons.push(name(b) + (b.disabled ? ' (disabled)' : ''));
  for (const a of document.querySelectorAll('a[href]')) if (vis(a) && !a.closest('header, footer, nav')) out.links.push(name(a) + ' -> ' + a.getAttribute('href'));
  for (const i of document.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not([type=submit]), textarea')) if (vis(i)) out.inputs.push(label(i) + ' [' + (i.type || 'text') + ']');
  for (const s of document.querySelectorAll('select')) if (vis(s)) out.selects.push(label(s) + ': ' + [...s.options].map(o => o.text).slice(0, 6).join('|'));
  for (const t of document.querySelectorAll('input[type=checkbox], input[type=radio], [role=switch], [role=tab], [aria-pressed]')) if (vis(t)) out.toggles.push((t.getAttribute('role') || t.type) + ': ' + (label(t) || name(t)));
  for (const t of document.querySelectorAll('[data-testid]')) out.testids.push(t.getAttribute('data-testid'));
  out.testids = [...new Set(out.testids)];
  out.buttons = [...new Set(out.buttons)]; out.links = [...new Set(out.links)].slice(0, 40);
  out.text = document.body.innerText;
  return out;
}"""
NUMBERS = re.compile(r"(?:[$₹]\s?-?[\d,]+(?:\.\d+)?|-?[$₹][\d,]+(?:\.\d+)?|\b\d+(?:\.\d+)?\s?(?:%|orders?|delivered|min|km|mi)\b|\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w* \d{1,2} \w{3}(?: \d{4})?)")


def main() -> int:
    for port, target in sw.FORWARD.items():
        sw.forward(port, target)
    out: list[dict] = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        sp = b.new_page()
        sw.setup(sp)
        sp.close()
        for market, (phone, _email, scope) in sw.USERS.items():
            for app, base, pages in (("web", sw.WEB, sw.WEB_PAGES), ("admin", sw.ADMIN, sw.ADMIN_PAGES + [("/", "/", True)])):
                ctx = b.new_context(viewport={"width": 1440, "height": 900})
                if app == "web":
                    ctx.add_cookies([{"name": "bg_city", "value": "US-ID-BOI" if market == "us" else "IN-TG-HYD", "url": sw.WEB}])
                page = ctx.new_page()
                signed = False
                for route, how, auth in pages:
                    if auth and not signed:
                        signed = sw.sign_in(page, app, market, phone)
                    try:
                        url = sw.resolve(page, app, base, how.replace("{scope}", scope), market)
                        if not url:
                            out.append({"app": app, "route": route, "user": market, "skip": True})
                            continue
                        page.goto(url, wait_until="networkidle", timeout=45000)
                        page.wait_for_timeout(500)
                        inv = page.evaluate(INVENTORY_JS)
                        text = inv.pop("text")
                        inv["numbers"] = sorted(set(NUMBERS.findall(text)))[:60]
                        out.append({"app": app, "route": route, "user": market, "url": page.url.replace(base, ""), **inv})
                    except Exception as e:  # noqa: BLE001
                        out.append({"app": app, "route": route, "user": market, "error": str(e)[:200]})
                    print(app, route, market, flush=True)
                ctx.close()
        b.close()
    with open(f"{sw.OUT}/explore.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
