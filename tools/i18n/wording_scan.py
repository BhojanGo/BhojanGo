"""User-visible wording we don't use, in every language (was kitchen_scan.py). Each term in TERMS:

  * kitchen (R30): no customer- or restaurant-facing "kitchen" (it's a restaurant)
  * bag / basket (R33): the customer's order before paying is a "cart" (Cart, Add to cart, View cart). The
    insulated delivery bags a delivery partner carries and a restaurant packs are real bags: those locale keys
    are allowed (BAG.allowed_keys).

Lists every user-visible string that still says one:

  * locale values (packages/i18n/messages/*.json), in every language: the English word and each language's own
  * string literals and JSX text in the apps and shared packages (tests, stories and code identifiers aside:
    a string with no space that looks like a key, path, test id or route is code, not copy)
  * user-facing backend strings (string constants in core_api, docstrings aside) and the seeded help / legal text

    python tools/i18n/wording_scan.py            # prints each hit; exit 1 if any
    python tools/i18n/wording_scan.py --summary  # counts only

Code identifiers (KitchenCard, kitchen_join, /kitchens/join, bag_paused, useBag...) stay: they are not copy.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP_DIRS = {"node_modules", ".next", "dist", "build", ".expo", "test", "tests", "__tests__", ".maestro", "e2e", "android", "ios"}
CODE_EXT = {".ts", ".tsx", ".js", ".jsx"}
STRING = re.compile(r"""(?P<q>["'`])(?P<s>(?:\\.|(?!(?P=q)).)*?)(?P=q)""", re.S)
# JSX-text candidates that are really TypeScript between a ">" and a "<" (generics, comparisons, comments)
# R38: what a "}...{" span looks like when it is code, not JSX text
BETWEEN_CODE = re.compile(r"\bimport\b|\bfrom\s+[\"']|\w=\s*$|^\s*[,;:)\]]|\btype \w+ =|//|===|\baria-|\bon[A-Z]\w*=|^\s*[\"'`]|[\"'`]\s*$|=\s*[\"'`{]")
CODEISH = re.compile(r"\bif \(|: Record|; //|=>|&&|\|\||\bconst\b|\breturn\b|: [A-Z]\w*<|\w\(|\)\s*[;{]|^\s*//|\*/|/\*")
ICU = re.compile(r"\{[^{}]*\}")  # a message's {placeholder}: a variable name, not copy
PLACE = re.compile(r"\$\{[^{}]*\}")  # a template literal's ${...}: code
NOTHING = re.compile(r"(?!x)x")


@dataclass(frozen=True)
class Term:
    name: str
    word: re.Pattern  # cheap pre-filter
    prose: re.Pattern  # the word in prose (not an identifier, path or key)
    native: dict  # per locale: [0] the English word(s), then the language's own words (regex strings)
    names: re.Pattern = NOTHING  # trading names that contain the word (allowed)
    one_word: tuple = ()  # one-word labels that are copy (aria-label, data-label, a tab)
    allowed_keys: frozenset = field(default_factory=frozenset)  # locale keys where the word means something else
    allowed_text: re.Pattern = NOTHING  # phrases where it means something else (in code, backend and help text)

    def jsx_text(self) -> re.Pattern:
        """JSX text with the word in it (also across lines: text on its own line)."""
        return re.compile(r">([^<>{}]*(?:" + self.word.pattern + r")[^<>{}]*)<", re.I)

    def jsx_between(self) -> re.Pattern:
        """R38: JSX text between expressions on one line ("{m(x)} · kitchen payouts{" "}")."""
        w = self.word.pattern
        return re.compile(r"[>}]([^<>{}\n]*(?:" + w + r")[^<>{}\n]*)\{|\}([^<>{}]*(?:" + w + r")[^<>{}]*)<", re.I)


KITCHEN = Term(
    "kitchen", re.compile(r"kitchen", re.I),
    # the word in prose, not kitchen_id / #kitchens / kitchen.name
    re.compile(r"(?<![#/.\w-])kitchens?(?![\w-]|\.\w)", re.I),
    {"en": [r"kitchen"],
     "es": [r"kitchen", r"\bcocinas?\b"],
     "hi": [r"kitchen", "रसोई", "किचन"],
     "bn": [r"kitchen", "রান্নাঘর", "কিচেন"],
     "mr": [r"kitchen", "स्वयंपाकघर", "किचन"],
     "ta": [r"kitchen", "சமையலறை", "கிச்சன்"],
     "te": [r"kitchen", "వంటగది", "వంటశాల", "కిచెన్"],
     "kn": [r"kitchen", "ಅಡುಗೆಮನೆ", "ಕಿಚನ್"]},
    # A restaurant's own trading name (demo seed data) is the business's name, not BhojanGo's wording: allowed.
    names=re.compile(r"\b(Spice Route|Basque Corner|Kesar) Kitchen\b"),
    one_word=("Kitchen", "Kitchens"),
)

EN_BAG = r"\bbags?\b|\bbaskets?\b"
# Tamil has no \b: "pai" (bag) with its case endings, not inside a longer Tamil word
TA_BAG = r"(?<![஀-௿])பை(?:யில்|யை|க்கு)?(?![஀-௿])"
BAG = Term(
    "bag/basket", re.compile(r"bag|basket", re.I),
    re.compile(r"(?<![#/.\w-])(?:bags?|baskets?)(?![\w-]|\.\w)", re.I),
    {"en": [EN_BAG],
     "es": [EN_BAG, r"\bbolsas?\b", r"\bcestas?\b", r"\bcanastas?\b"],
     "hi": [EN_BAG, "बैग", "थैला", "थैले", "टोकरी"],
     "bn": [EN_BAG, "ব্যাগ", "থলে", "ঝুড়ি"],
     "mr": [EN_BAG, "बॅग", "पिशवी", "टोपली"],
     "ta": [EN_BAG, TA_BAG, "கூடை"],  # not "பேக்": it is also pack, packaging and bakery
     "te": [EN_BAG, "బ్యాగ్", "సంచి", "బుట్ట"],
     "kn": [EN_BAG, "ಬ್ಯಾಗ್", "ಚೀಲ", "ಬುಟ್ಟಿ"]},
    one_word=("Bag", "Bags", "Basket"),
    # the insulated delivery bags a delivery partner carries and a restaurant packs: real bags, not the cart
    allowed_keys=frozenset({"rider.offer.bags.one", "rider.offer.bags.other", "rider.delivery.take_photo",
                            "rider.delivery.ready_pickup", "rider.delivery.in_bag",
                            "partner.orders.bags.one", "partner.orders.bags.other"}),
    # the same real bags in the partner and restaurant help and the delivery-photo prompt
    allowed_text=re.compile(r"photo of the bags|order code on the bag|fotos? de las bolsas|código del pedido en la bolsa"
                            r"|बैग पर ऑर्डर कोड"
                            r"|जहाँ बैग रखे", re.I),
)
TERMS = (KITCHEN, BAG)


def flat(d: dict, p: str = ""):  # type: ignore[no-untyped-def]
    for k, v in d.items():
        if isinstance(v, dict):
            yield from flat(v, p + k + ".")
        else:
            yield p + k, v


def is_code(s: str, t: Term = KITCHEN) -> bool:
    """A key, identifier, path, route, test id, import or CSS: not something a person reads."""
    s = t.names.sub("", s).strip()
    if not s or " " not in s:
        return True
    return bool(re.fullmatch(r"[\w./:@#?=&${}\-\[\]()*,]+", s))


def locale_hits(t: Term = KITCHEN) -> list[str]:
    out = []
    for f in sorted((ROOT / "packages/i18n/messages").glob("*.json")):
        pats = [re.compile(p, re.I) for p in t.native.get(f.stem, t.native["en"])]
        for k, v in flat(json.loads(f.read_text(encoding="utf-8"))):
            if k in t.allowed_keys:
                continue
            if isinstance(v, str) and any(p.search(ICU.sub("", v)) for p in pats):
                out.append(f"{f.relative_to(ROOT)}: {k} = {v[:120]!r}")
    return out


def code_hits(t: Term = KITCHEN) -> list[str]:
    out = []
    jsx = t.jsx_text()
    for base in ("apps", "packages"):
        for f in (ROOT / base).rglob("*"):
            if f.suffix not in CODE_EXT or any(part in SKIP_DIRS for part in f.parts) or ".test." in f.name:
                continue
            if "i18n" in f.parts and f.name in ("all-messages.js", "all-messages.d.ts"):
                continue  # generated from the locale files, checked above
            text = f.read_text(encoding="utf-8", errors="ignore")
            if not t.word.search(text):
                continue
            if f.suffix in (".tsx", ".jsx"):
                seen = set()
                for pat, strict in ((jsx, False), (t.jsx_between(), True)):
                    for m in pat.finditer(text):
                        body = m.group(1) if m.group(1) is not None else m.group(2)
                        if strict and BETWEEN_CODE.search(body):
                            continue
                        if t.prose.search(t.names.sub("", body)) and not CODEISH.search(body):
                            n = text.count(chr(10), 0, m.start(1 if m.group(1) is not None else 2) + len(body) - len(body.lstrip())) + 1
                            hit = f"{f.relative_to(ROOT)}:{n}: {' '.join(body.split())[:120]!r}"
                            if hit not in seen:
                                seen.add(hit)
                                out.append(hit)
            for n, line in enumerate(text.splitlines(), 1):
                if not t.word.search(line) or line.lstrip().startswith(("//", "*", "/*", "{/*", "import ")):
                    continue
                found = [m.group("s") for m in STRING.finditer(line)]
                # R38: strings inside a template literal's ${...} ("paid by ${x ? "the kitchen" : ...}")
                found += [m.group("s") for f_ in found for inner in re.findall(r"\$\{([^{}]*)\}", f_) for m in STRING.finditer(inner)]
                for s in found:
                    if t.allowed_text.search(s):
                        continue
                    if s in t.one_word:  # a one-word label (aria-label, data-label, a tab): copy, not code
                        out.append(f"{f.relative_to(ROOT)}:{n}: {s!r}")
                        continue
                    bare = PLACE.sub("", s)
                    if (t.word.search(bare) and not is_code(bare, t) and not s.lstrip().startswith(("//", "/*"))
                            and "=>" not in s and ": Record" not in s and t.prose.search(s)):
                        out.append(f"{f.relative_to(ROOT)}:{n}: {s[:120]!r}")
    return out


def config_hits(t: Term = KITCHEN) -> list[str]:
    """App names and permission prompts in apps/*/app.json (what the stores and the phone show)."""
    out = []
    for f in sorted((ROOT / "apps").glob("*/app.json")):
        def walk(v, path=""):  # type: ignore[no-untyped-def]
            if isinstance(v, dict):
                for k, x in v.items():
                    walk(x, f"{path}.{k}")
            elif isinstance(v, list):
                for i, x in enumerate(v):
                    walk(x, f"{path}[{i}]")
            elif isinstance(v, str) and " " in v and t.prose.search(v):
                out.append(f"{f.relative_to(ROOT)}: {path} = {v[:120]!r}")
        walk(json.loads(f.read_text(encoding="utf-8")))
    return out


def _native(t: Term, langs: list[str]) -> list[re.Pattern]:
    """Each language's own words (not the English ones, which t.prose covers)."""
    return [re.compile(w, re.I) for lang in langs for w in t.native.get(lang, [])[1:]]


def python_hits(t: Term = KITCHEN) -> list[str]:
    out = []
    native = _native(t, [lang for lang in t.native if lang != "en"])
    files = [f for d in ("core_api", "shared", "realtime/app", "worker/app", "tools") for f in (ROOT / "backend" / d).rglob("*.py")]
    for f in files:
        if any(part in ("tests", "integration", "migrations") for part in f.parts) or f.name.endswith("_test.py"):
            continue
        text = f.read_text(encoding="utf-8")
        if not t.word.search(text) and not any(w.search(text) for w in native):
            continue
        tree = ast.parse(text)
        docs = {id(n.body[0].value) for n in ast.walk(tree)
                if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs:
                v = ICU.sub("", t.names.sub("", n.value))
                if t.allowed_text.search(v):
                    continue
                if (t.prose.search(v) or any(w.search(v) for w in native)) and not is_code(n.value, t):
                    out.append(f"{f.relative_to(ROOT)}:{n.lineno}: {n.value[:120]!r}")
    return out


def content_hits(t: Term = KITCHEN) -> list[str]:
    """Help articles and legal documents, in every language (links and slugs like /help/add-your-kitchen are code)."""
    out = []
    for base in ("tools/seed/help", "tools/seed/legal"):
        for f in sorted((ROOT / base).rglob("*.md")):
            lang = f.parent.name if base.endswith("help") else "en"
            native = _native(t, [lang])
            for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if line.startswith(("slug:", "related:", "id:")):
                    continue
                text = t.names.sub("", re.sub(r"\]\([^)]*\)", "]", line))
                if t.allowed_text.search(text):
                    continue
                if t.prose.search(text) or any(w.search(text) for w in native):
                    out.append(f"{f.relative_to(ROOT)}:{n}: {line.strip()[:120]!r}")
    return out


def self_test() -> int:
    """The matchers find copy and leave code alone (each case is a bug this scanner once had)."""
    K, B = KITCHEN, BAG
    prose = ["Search dishes and kitchens", "what the kitchen is paid.", "Kitchen's treat", "KITCHEN"]
    code = ["kitchen_id", "#kitchens", "/kitchens/join", "kitchen.name", "kitchenQ", "add-your-kitchen"]
    assert all(K.prose.search(t) for t in prose), prose
    assert not any(K.prose.search(t) for t in code), code
    jsx = ">\n        Test site: demo kitchens, no real orders or payments\n      <"  # JSX text on its own line
    assert [m.group(1) for m in K.jsx_text().finditer(jsx) if not CODEISH.search(m.group(1))]
    for ts in (">, kitchens: Record<", "> 0; if (kitchen) return <", ">a; // the kitchen's x <"):  # TypeScript, not text
        assert CODEISH.search(K.jsx_text().search(ts).group(1)), ts
    assert re.search(r"\bcocinas?\b", "Repartidor en camino a la cocina", re.I)
    assert ICU.sub("", "Order again from {kitchen}") == "Order again from "
    # R38: JSX text between expressions, and strings inside a template literal's ${...}
    between = KITCHEN.jsx_between()
    m = between.search('{m(x)} · kitchen payouts{" "}')
    assert m and "kitchen payouts" in (m.group(1) or m.group(2))
    assert not any(BETWEEN_CODE.search(x.group(1) or x.group(2)) is None
                   for x in between.finditer('} from "../[country]/[city]/[kitchen]/data";\nimport x from "y";<'))
    tpl = '`paid by ${p.funded_by === "restaurant" ? "the kitchen" : "BhojanGo"}`'
    inner = [m.group("s") for f_ in [x.group("s") for x in STRING.finditer(tpl)]
             for i in re.findall(r"\$\{([^{}]*)\}", f_) for m in STRING.finditer(i)]
    assert "the kitchen" in inner
    assert K.names.sub("", "Spice Route Kitchen").strip() == "" and is_code("Spice Route Kitchen")
    # R33: bag / basket
    assert all(B.prose.search(t) for t in ["Add to bag", "Your bag is empty", "View Bag", "a basket"])
    assert not any(B.prose.search(t) for t in ["bag_paused", "useBag", "/bag", "bag.lines", "baggage", "airbag"])
    ta = re.compile(TA_BAG)
    assert ta.search("உங்கள் பை காலியாக") and ta.search("பையில் சேர்") and not ta.search("பைக் ஓட்டுநர்")  # bike
    assert B.allowed_text.search("Take a photo of the bags at the door") and not B.allowed_text.search("Your bag")
    assert B.allowed_text.search("2. बैग पर ऑर्डर कोड जांचें।")
    assert re.search("बैग", "आपका बैग खाली है") and not re.search("बैग", "आपका कार्ट खाली है")
    print("wording_scan self-test ok")
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    total = 0
    for t in TERMS:
        groups = {"locales": locale_hits(t), "app and package strings": code_hits(t), "app configs": config_hits(t),
                  "backend strings": python_hits(t), "help and legal": content_hits(t)}
        n = sum(len(v) for v in groups.values())
        total += n
        print(f"[{t.name}]")
        for name, hits in groups.items():
            print(f"  {name}: {len(hits)}")
            if "--summary" not in sys.argv:
                for h in hits:
                    print("    " + h)
        print(f"  {t.name} total: {n}")
    print(f"total: {total}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
