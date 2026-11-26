"""R44: a run leaves nothing behind. Every test removes what it makes (dishes, categories, option groups, offers,
accounts, restaurants, help drafts); this check proves it on the stack's test database.

  python leftovers.py snapshot     before the run: what the seeded stack has  -> $OUT/leftovers-before.json
  python leftovers.py check        after the run: anything new that is still live, and anything with a test name
                                   ("R42 …", "R44-…"), wherever it came from  -> $OUT/leftovers.json; exit 1 if any

"Still live": a dish or option group not deleted, any category, an offer or fee rule not ended (draft, waiting for
approval, or published with no end), an active account, a restaurant not deleted and active, any help article.
Orders, payments, tickets and the history rows they carry are records, not test furniture: not checked.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(HERE), "/guard"]
from framework import sql  # noqa: E402

OUT = os.environ.get("OUT_DIR", "/out")
TEST_NAME = r"^R4[0-9]([ _-]|$)"
TEST_RE = re.compile(TEST_NAME, re.I)

# (kind, the query for what's live: id, a label)
LIVE = {
    "dish": "SELECT m.id::text, r.name || ': ' || m.name FROM menu_items m JOIN restaurants r ON r.id = m.restaurant_id "
            "WHERE m.deleted_at IS NULL",
    "category": "SELECT c.id::text, r.name || ': ' || c.name FROM menu_categories c JOIN restaurants r ON r.id = c.restaurant_id",
    "option group": "SELECT g.id::text, r.name || ': ' || g.name FROM option_groups g JOIN restaurants r ON r.id = g.restaurant_id",
    "option": "SELECT o.id::text, g.name || ': ' || o.name FROM options o JOIN option_groups g ON g.id = o.group_id",
    "offer or rule": "SELECT id::text, family || ' ' || coalesce(name, key, '') FROM rules WHERE status IN ('draft', 'pending_approval') "
                     "OR (status = 'published' AND (effective_to IS NULL OR effective_to > now()))",
    "account": "SELECT id::text, coalesce(email, phone, '') || ' (' || coalesce(full_name, '') || ', ' || role::text || ')' FROM users "
               "WHERE is_active",
    "restaurant": "SELECT id::text, name FROM restaurants WHERE deleted_at IS NULL AND is_active",
    "help article": "SELECT id::text, slug || ': ' || title FROM help_articles",
}


def live() -> dict[str, dict[str, str]]:
    return {k: {i: label for i, label in sql(q)} for k, q in LIVE.items()}


def main(step: str) -> int:
    before_file = f"{OUT}/leftovers-before.json"
    if step == "snapshot":
        json.dump(live(), open(before_file, "w", encoding="utf-8"), ensure_ascii=False)
        print("leftovers: snapshot", {k: len(v) for k, v in live().items()})
        return 0
    before = json.load(open(before_file, encoding="utf-8"))
    now = live()
    found = []
    for kind, rows in now.items():
        for i, label in rows.items():
            name = label.split(": ", 1)[-1]
            new = i not in before.get(kind, {})
            if new or TEST_RE.search(name):
                found.append({"kind": kind, "id": i, "label": label, "why": "made by the run, still live" if new else "a test name"})
    json.dump({"found": found, "before": {k: len(v) for k, v in before.items()}, "after": {k: len(v) for k, v in now.items()}},
              open(f"{OUT}/leftovers.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    for f in found:
        print(f"LEFTOVER {f['kind']}: {f['label']} ({f['why']})")
    print(f"leftovers: {len(found)}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "check"))
