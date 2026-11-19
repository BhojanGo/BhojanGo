"""Production config dry run: what the code needs vs what .railway/railway.ts gives production.

Read-only. No network, no Railway CLI, no secrets: it reads the repository only and prints
variable NAMES and a kind (sealed, set, empty, reference), never a value.

    python tools/railway/prod_config_check.py          # exit 1 when there are gaps

What it reads:
- backend/shared/config.py: every Settings field (the environment variable names the backends read);
- os.environ reads in the backend, process.env reads in web/admin, EXPO_PUBLIC_* in the apps;
- worker/app/main.py: _REQUIRED_PROD_SETTINGS (the worker refuses to start without them);
- infra/docker/next-app.Dockerfile: build args and the variables derived from them;
- .railway/railway.ts, evaluated for the production environment by a small parser
  (object literals, spreads, `prod ? a : b`, `const` bindings and the helper functions).
The list of what production needs (REQUIRED below) points at the code line that needs it.
See docs/launch/production-config.md.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAILWAY_TS = ROOT / ".railway" / "railway.ts"
BACKEND = ROOT / "backend"


# ── A small evaluator for railway.ts ─────────────────────────────────────────

@dataclass
class Val:
    kind: str  # by-hand (preserve(): set outside the file; secrets sealed) | empty | set | reference | computed | unknown
    value: str | None = None  # kept for the checks only; never printed


def strip_comments(src: str) -> str:
    out, i, n, q = [], 0, len(src), None
    while i < n:
        c = src[i]
        if q:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(src[i + 1])
                i += 2
                continue
            if c == q:
                q = None
        elif c in "'\"`":
            q = c
            out.append(c)
        elif src.startswith("//", i):
            while i < n and src[i] != "\n":
                i += 1
            continue
        elif src.startswith("/*", i):
            i = src.index("*/", i) + 2
            continue
        else:
            out.append(c)
        i += 1
    return "".join(out)


def scan(s: str):
    """Yield (index, char, depth) for characters outside strings."""
    depth, q, i = 0, None, 0
    while i < len(s):
        c = s[i]
        if q:
            if c == "\\":
                i += 2
                continue
            if c == q:
                q = None
        elif c in "'\"`":
            q = c
        else:
            if c in ")]}":
                depth -= 1
            yield i, c, depth
            if c in "([{":
                depth += 1
        i += 1


def split_top(s: str, sep: str) -> list[str]:
    parts, last = [], 0
    for i, c, d in scan(s):
        if c == sep and d == 0:
            parts.append(s[last:i])
            last = i + 1
    parts.append(s[last:])
    return [p for p in (x.strip() for x in parts) if p]


def matching(s: str, start: int) -> int:
    for i, c, d in scan(s):
        if i > start and c in ")]}" and d == 0:
            return i
    raise ValueError("unbalanced: " + s[start:start + 40])


def top_index(s: str, ch: str) -> int:
    for i, c, d in scan(s):
        if c == ch and d == 0:
            return i
    return -1


def ternary(e: str):
    for i, c, d in scan(e):
        if c == "?" and d == 0 and e[i + 1:i + 2] not in ("?", ".", ":"):
            nest = 0
            for j, c2, d2 in scan(e):
                if j <= i or d2 != 0:
                    continue
                if c2 == "?":
                    nest += 1
                elif c2 == ":":
                    if nest == 0:
                        return e[:i], e[i + 1:j], e[j + 1:]
                    nest -= 1
    return None


class Env:
    def __init__(self, flags: dict[str, bool], bindings: dict[str, str]):
        self.flags, self.b = flags, bindings

    def truth(self, cond: str) -> bool:
        expr = cond.replace("||", " or ").replace("&&", " and ")
        expr = re.sub(r"!(?!=)", " not ", expr)
        names = set(re.findall(r"[A-Za-z_][\w.]*", expr)) - {"or", "and", "not"}
        if not names <= set(self.flags):
            return False  # e.g. opts.preDeploy: not about variables
        return bool(eval(expr, {"__builtins__": {}}, dict(self.flags)))  # noqa: S307 - only our bool flags

    def ev(self, e: str):
        e = e.strip()
        t = ternary(e)
        if t:
            return self.ev(t[1] if self.truth(t[0]) else t[2])
        if e.startswith("(") and matching(e, 0) == len(e) - 1:
            return self.ev(e[1:-1])
        if e.startswith("{"):
            return self.obj(e)
        if e == "preserve()":
            return Val("by-hand")
        if e[:1] in "'\"":
            v = e[1:-1]
            return Val("empty" if v == "" else "reference" if "${{" in v else "set", v)
        if e[:1] == "`":
            return Val("reference" if "${{" in e else "set", e[1:-1])
        if re.match(r"^[\w.]+\(", e):
            return Val("reference" if e.startswith("redisDb(") else "computed")
        if re.fullmatch(r"[A-Za-z_]\w*", e) and e in self.b:
            return self.ev(self.b[e])
        return Val("unknown")

    def raw_obj(self, e: str) -> tuple[dict[str, str], list[str]]:
        keys, spreads = {}, []
        for p in split_top(e.strip()[1:-1], ","):
            if p.startswith("..."):
                spreads.append(p[3:])
                continue
            k = top_index(p, ":")
            keys[p[:k].strip().strip("'\"")] = p[k + 1:]
        return keys, spreads

    def obj(self, e: str) -> dict:
        out: dict = {}
        for p in split_top(e.strip()[1:-1], ","):
            if p.startswith("..."):
                v = self.ev(p[3:])
                if isinstance(v, dict):
                    out.update(v)
                continue
            k = top_index(p, ":")
            out[p[:k].strip().strip("'\"")] = self.ev(p[k + 1:])
        return out


def railway_env(environment: str) -> dict[str, dict[str, Val]]:
    """Each service's variables in one environment, as railway.ts defines them."""
    src = strip_comments(RAILWAY_TS.read_text(encoding="utf-8"))
    start = src.index("defineRailway(")
    body_open = src.index("{", src.index("=>", start))
    body = src[body_open + 1:matching(src, body_open)]
    bindings: dict[str, str] = {}
    for stmt in split_top(body, ";"):
        m = re.match(r"^const\s+(\w+)(?:\s*:\s*\w+)?\s*=\s*(.*)$", stmt, re.S)
        if m:
            bindings[m.group(1)] = m.group(2)
    flags = {"prod": environment == "production", "qa": environment == "QA"}
    env = Env(flags, bindings)
    services: dict[str, dict[str, Val]] = {}
    for name, expr in bindings.items():
        m = re.match(r"^(\w+)\(", expr)
        if not m:
            continue
        fn = m.group(1)
        args = split_top(expr[expr.index("(") + 1:matching(expr, expr.index("("))], ",")
        if fn == "service":
            local = env
            call = expr
        elif fn in bindings and "=>" in bindings[fn]:
            helper = bindings[fn]
            params = [re.split(r"[?:\s]", p.strip(), maxsplit=1)[0]
                      for p in split_top(helper[helper.index("(") + 1:matching(helper, helper.index("("))], ",")]
            local = Env(flags, {**bindings, **dict(zip(params, args))})
            call = helper[helper.index("=>") + 2:].strip()
            if not call.startswith("service("):
                continue
        else:
            continue
        cargs = split_top(call[call.index("(") + 1:matching(call, call.index("("))], ",")
        svc_name = local.ev(cargs[0])
        keys, _ = local.raw_obj(cargs[1])
        if isinstance(svc_name, Val) and svc_name.value and "env" in keys:
            services[svc_name.value] = local.ev(keys["env"])
    return services


# ── What the code reads ───────────────────────────────────────────────────────

def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def line_of(path: str, pattern: str) -> str:
    p = ROOT / path
    try:
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if pattern in line:
                return f"{path}:{n}"
    except OSError:
        pass
    return f"{path} (pattern not found: {pattern})"


def settings_fields() -> dict[str, str]:
    path = BACKEND / "shared" / "config.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = {}
    for cls in tree.body:
        if isinstance(cls, ast.ClassDef) and any(getattr(b, "id", "") == "BaseSettings" for b in cls.bases):
            for node in cls.body:
                if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id.isupper():
                    out[node.target.id] = f"{rel(path)}:{node.lineno}"
    return out


def code_files(base: Path, exts: tuple[str, ...]):
    skip = ("node_modules", ".venv", ".next", "dist", "__pycache__", "/tests/", "/test/", "integration", "/e2e/")
    for p in base.rglob("*"):
        s = p.as_posix()
        if p.suffix in exts and p.is_file() and not any(x in s for x in skip) \
                and not p.name.startswith(("test_", "conftest")) and ".test." not in p.name:
            yield p


def regex_reads(bases: list[Path], exts: tuple[str, ...], pattern: str) -> dict[str, str]:
    out: dict[str, str] = {}
    rx = re.compile(pattern)
    for base in bases:
        files = [base] if base.is_file() else code_files(base, exts)
        for p in files:
            for n, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                for name in rx.findall(line):
                    out.setdefault(name, f"{rel(p)}:{n}")
    return out


def worker_required() -> tuple[list[str], str]:
    path = BACKEND / "worker" / "app" / "main.py"
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "_REQUIRED_PROD_SETTINGS":
            return [e.value for e in node.value.elts], f"{rel(path)}:{node.lineno}"  # type: ignore[attr-defined]
    return [], rel(path)


def dockerfile() -> tuple[set[str], dict[str, str]]:
    text = (ROOT / "infra" / "docker" / "next-app.Dockerfile").read_text(encoding="utf-8")
    args = set(re.findall(r"^ARG\s+(\w+)", text, re.M))
    derived = dict(re.findall(r"(\w+)=\$\{(\w+)\}", text))  # NAME=${ARG}
    return args, derived


# ── What production needs (each points at the code that needs it) ─────────────
# rule: set | sealed (preserve() in railway.ts, a sealed variable in Railway) | live | not_fake | empty | off
BACKENDS = ("core-api", "realtime", "worker")
C, W = ("core-api",), ("worker",)
REQUIRED: list[tuple[str, tuple[str, ...], str, str, str]] = [
    ("APP_ENV", BACKENDS, "set", "backend/shared/config.py", "def is_production"),
    ("DATABASE_URL", ("core-api", "worker"), "set", "backend/shared/config.py", "DATABASE_URL: str"),
    ("REDIS_URL", BACKENDS, "set", "backend/shared/config.py", "REDIS_URL: str"),
    ("EVENT_BUS", BACKENDS, "set", "backend/worker/app/main.py", "EVENT_BUS=redis"),
    ("EVENT_BUS_REDIS_URL", BACKENDS, "set", "backend/shared/config.py", "EVENT_BUS_REDIS_URL"),
    ("INTERNAL_SERVICE_SECRET", BACKENDS, "sealed", "backend/shared/internal_auth.py", "must be set in production"),
    ("JWT_PRIVATE_KEY", C, "sealed", "backend/shared/config.py", "required in production (core_api)"),
    ("JWKS_URL", ("realtime", "worker"), "set", "backend/shared/config.py", "JWKS_URL: str"),
    ("CORE_API_URL", ("realtime", "worker"), "set", "backend/shared/config.py", "CORE_API_URL: str"),
    ("CORS_ORIGINS", ("core-api", "realtime"), "set", "backend/shared/config.py", "CORS_ORIGINS"),
    ("CLIENT_IP_HEADER", BACKENDS, "set", "backend/shared/config.py", "CLIENT_IP_HEADER"),
    ("PAYMENT_PROVIDER", BACKENDS, "live", "backend/shared/config.py", "if p.PAYMENT_PROVIDER != \"live\""),
    ("PAYOUT_PROVIDER", BACKENDS, "not_fake", "backend/shared/config.py", "if p.PAYOUT_PROVIDER == \"fake\""),
    ("OTP_FIXED_CODE", BACKENDS, "empty", "backend/shared/config.py", "if p.OTP_FIXED_CODE:"),
    ("DELIVERY_PIN_FIXED", BACKENDS, "empty", "backend/shared/config.py", "if p.DELIVERY_PIN_FIXED:"),
    ("DEMO_RIDER_SIM", W, "off", "backend/shared/config.py", "if self.worker.DEMO_RIDER_SIM"),
    ("IDENTITY_DATA_KEYS", C, "sealed", "backend/core_api/modules/identity/service/totp.py", "IDENTITY_DATA_KEYS is not set"),
    ("PUBLIC_WEB_URL", C, "set", "backend/core_api/modules/finance/service/connect.py", "PUBLIC_WEB_URL"),
    ("PUBLIC_API_URL", C, "set", "backend/core_api/modules/finance/service/connect.py", "PUBLIC_API_URL"),
    ("STRIPE_SECRET_KEY", C, "sealed", "backend/core_api/modules/payments/service/gateways.py", "return bool(p.STRIPE_SECRET_KEY)"),
    ("STRIPE_PUBLISHABLE_KEY", C, "set", "backend/core_api/modules/payments/service/gateways.py", "STRIPE_PUBLISHABLE_KEY"),
    ("STRIPE_WEBHOOK_SECRET", C, "sealed", "backend/core_api/modules/payments/service/stripe_svc.py", "STRIPE_WEBHOOK_SECRET"),
    ("STRIPE_CONNECT_WEBHOOK_SECRET", C, "sealed", "backend/core_api/modules/finance/api/v1/finance.py", "STRIPE_CONNECT_WEBHOOK_SECRET"),
    ("STRIPE_PAYOUTS_WEBHOOK_SECRET", C, "sealed", "backend/core_api/modules/finance/api/v1/finance.py", "STRIPE_PAYOUTS_WEBHOOK_SECRET"),
    ("SMS_PROVIDER", W, "live", "backend/shared/providers/sms.py", "refuse_in_production"),
    ("EMAIL_PROVIDER", W, "set", "backend/shared/providers/email.py", "refuse_in_production"),
    ("PUSH_PROVIDER", W, "live", "backend/shared/providers/push.py", "refuse_in_production"),
    ("TWILIO_AUTH_TOKEN", W, "sealed", "backend/shared/providers/sms.py", "TWILIO_AUTH_TOKEN"),
    ("TWILIO_PHONE_NUMBER", W, "set", "backend/shared/providers/sms.py", "TWILIO_PHONE_NUMBER"),
    ("SENDGRID_FROM_EMAIL", W, "set", "backend/shared/providers/email.py", "SENDGRID_FROM_EMAIL"),
    ("FIREBASE_PRIVATE_KEY_ID", W, "sealed", "backend/worker/app/services/fcm.py", "FIREBASE_PRIVATE_KEY_ID"),
    ("FIREBASE_PRIVATE_KEY", W, "sealed", "backend/worker/app/services/fcm.py", "FIREBASE_PRIVATE_KEY"),
    ("FIREBASE_CLIENT_EMAIL", W, "set", "backend/worker/app/services/fcm.py", "FIREBASE_CLIENT_EMAIL"),
    ("STORAGE_PROVIDER", C, "set", "backend/shared/providers/storage.py", "STORAGE_PROVIDER"),
    ("UPLOADS_BUCKET", C, "set", "backend/shared/config.py", "UPLOADS_BUCKET"),
    ("AWS_ACCESS_KEY_ID", C, "sealed", "backend/shared/providers/storage.py", "aws_access_key_id"),
    ("AWS_SECRET_ACCESS_KEY", C, "sealed", "backend/shared/providers/storage.py", "aws_access_key_id"),
    ("AWS_ENDPOINT_URL", C, "set", "backend/shared/config.py", "AWS_ENDPOINT_URL"),
    ("ALERT_WEBHOOK_TOKEN", C, "sealed", "backend/shared/config.py", "ALERT_WEBHOOK_TOKEN"),
    ("POSTGRES_PASSWORD", ("postgres",), "sealed", ".railway/railway.ts", "POSTGRES_PASSWORD"),
    # Frontends (build args and run time)
    ("APP_ENV", ("web", "admin"), "set", "apps/web/src/lib/server.ts", "INDEXABLE"),
    ("NEXT_PUBLIC_CORE_URL", ("web", "admin"), "set", "apps/web/next.config.mjs", "NEXT_PUBLIC_CORE_URL"),
    ("NEXT_PUBLIC_REALTIME_URL", ("web", "admin"), "set", "apps/web/next.config.mjs", "NEXT_PUBLIC_REALTIME_URL"),
    ("NEXT_PUBLIC_APP_URL", ("web",), "set", "apps/web/src/lib/server.ts", "NEXT_PUBLIC_APP_URL"),
    ("CORE_API_INTERNAL_URL", ("web",), "set", "apps/web/src/lib/server.ts", "CORE_API_INTERNAL_URL"),
    ("CORE_API_URL", ("web", "admin"), "set", "apps/admin/next.config.mjs", "must be set in production"),
    ("NEXT_PUBLIC_PAYMENTS_PROVIDER", ("web",), "not_fake", "apps/web/src/app/account/profile/Payments.tsx", "NEXT_PUBLIC_PAYMENTS_PROVIDER"),
]
# Set in production but only meant for the fakes, the demo or QA.
QA_ONLY = ["FAKE_PAYMENT_WEBHOOK_URL", "FAKE_PAYMENT_AUTO_COMPLETE_SECONDS", "FAKE_PAYMENT_WEBHOOK_SECRET",
           "DEMO_RIDER_SIM", "SEED_PASSWORDS", "APNS_SANDBOX", "JWT_SECRET"]
FAKE_VALUES = {"fake", "log", "auto", "local", "smtp", "1", "true"}
OPTIONAL = {  # production can start without these; each turns a feature on
    "SENTRY_DSN": "error tracking (also needs sentry-sdk in backend/pyproject.toml)",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "traces",
    "GOOGLE_WEB_CLIENT_ID": "Sign in with Google on the website (GOOGLE_CLIENT_IDS for the apps)",
    "APPLE_CLIENT_ID": "Sign in with Apple",
    "EXPO_ACCESS_TOKEN": "Expo push security",
    "APNS_KEY_ID": "direct APNs push (iOS tokens not from Expo)",
    "TAX_PROVIDER": "explicit stripe_tax (auto picks Stripe Tax when STRIPE_SECRET_KEY is set)",
    "TWILIO_PHONE_NUMBER_IN": "India SMS (not Boise)",
    "MSG91_AUTH_KEY": "India SMS (not Boise)",
    "RAZORPAY_KEY_ID": "India payments (not Boise)",
}


def check(v: Val | None, rule: str) -> str | None:
    """None when the value passes; otherwise the problem (no value in the text)."""
    if v is None or not isinstance(v, Val):
        return None if rule == "off" else "not defined for production"
    if rule == "sealed" and v.kind != "by-hand":
        return f"a secret written in railway.ts ({v.kind}); use preserve() and a sealed variable"
    if rule in ("set", "sealed") and v.kind in ("empty", "unknown"):
        return f"defined as {v.kind}"
    if rule == "live" and (v.kind != "set" or v.value not in ("live", "sendgrid")):
        return "not a live provider"
    if rule == "not_fake" and v.kind == "set" and (v.value or "").lower() in FAKE_VALUES:
        return "a fake or fall-back value"
    if rule == "empty" and v.kind != "empty":
        return "must be defined as an empty string"
    if rule == "off" and v.kind == "set" and (v.value or "").lower() in ("1", "true", "yes", "on"):
        return "is on"
    return None


def main() -> int:
    prod = railway_env("production")
    gaps: list[str] = []
    print("Production config dry run (names only; no values, no network)\n")
    print(f"railway.ts, production: {len(prod)} services with variables: {', '.join(sorted(prod))}")
    for svc in sorted(prod):
        kinds: dict[str, list[str]] = {}
        for name, v in sorted(prod[svc].items()):
            kinds.setdefault(v.kind if isinstance(v, Val) else "object", []).append(name)
        print(f"  {svc}: " + "; ".join(f"{k} {len(n)} ({', '.join(n)})" for k, n in sorted(kinds.items())))

    fields = settings_fields()
    env_reads = regex_reads([BACKEND / d for d in ("core_api", "realtime", "worker", "shared")], (".py",),
                            r"os\.(?:environ\.get|getenv)\(\s*\"([A-Z][A-Z0-9_]+)\"")
    web_reads = regex_reads([ROOT / "apps/web/src", ROOT / "apps/web/next.config.mjs"], (".ts", ".tsx", ".mjs"),
                            r"process\.env\.([A-Z][A-Z0-9_]+)")
    admin_reads = regex_reads([ROOT / "apps/admin/src", ROOT / "apps/admin/next.config.mjs"], (".ts", ".tsx", ".mjs"),
                              r"(?:process\.env\.|svc\(\")([A-Z][A-Z0-9_]+)")
    expo_reads = regex_reads([ROOT / f"apps/{a}/{d}" for a in ("customer", "partner", "rider") for d in ("app", "lib", "components")
                              if (ROOT / f"apps/{a}/{d}").exists()] + [ROOT / "packages/mobile-core/src"],
                             (".ts", ".tsx", ".js"), r"process\.env\.(EXPO_PUBLIC_[A-Z0-9_]+)|env\(\"(EXPO_PUBLIC_[A-Z0-9_]+)\"")
    expo_names = sorted({n for pair in expo_reads for n in (pair if isinstance(pair, tuple) else (pair,)) if n})
    wreq, wreq_at = worker_required()
    args, derived = dockerfile()
    print(f"\nCode reads: {len(fields)} backend settings (config.py), {len(env_reads)} direct os.environ reads in the "
          f"backend, {len(web_reads)} web and {len(admin_reads)} admin process.env names, {len(expo_names)} EXPO_PUBLIC names.")

    # 1. Required for production
    required = list(REQUIRED) + [(n, W, "sealed" if "KEY" in n or "SID" in n else "set", wreq_at.split(":")[0],
                                  "_REQUIRED_PROD_SETTINGS") for n in wreq]
    print("\n1. What production needs, against railway.ts (production)")
    for name, services, rule, path, pattern in required:
        for svc in services:
            v = prod.get(svc, {}).get(name)
            if v is None and svc in ("web", "admin"):
                src = next((a for d, a in derived.items() if d == name), None)
                v = prod.get(svc, {}).get(src) if src else None
            problem = check(v, rule)
            if problem:
                gaps.append(f"{svc}: {name}: {problem} [needs: {rule}; {line_of(path, pattern)}]")
    for g in gaps:
        print("  GAP  " + g)
    if not gaps:
        print("  none")

    # 2. QA-only or fake settings that production would still get
    print("\n2. QA-only, demo or fake settings defined for production")
    warn = 0
    for svc, env in sorted(prod.items()):
        for name, v in sorted(env.items()):
            if not isinstance(v, Val):
                continue
            if name in QA_ONLY and not (v.kind == "empty" or (name == "DEMO_RIDER_SIM" and v.value in ("0", "false"))):
                print(f"  WARN {svc}: {name} is defined ({v.kind}); it only serves the fake gateway, the demo or QA")
                warn += 1
            if name.endswith("_PROVIDER") and v.kind == "set" and (v.value or "").lower() in FAKE_VALUES:
                print(f"  GAP  {svc}: {name} points at a fake, a log or an automatic fall-back")
                gaps.append(f"{svc}: {name} fake")
    if not warn:
        print("  none")

    # 3. Optional features: off in production unless set
    print("\n3. Optional (production starts without them; each is off until set)")
    for name, what in OPTIONAL.items():
        where = [s for s in BACKENDS if name in prod.get(s, {})]
        print(f"  {'set ' if where else 'off '} {name}: {what}")

    # 4. Frontend names read by code but not given by railway.ts or the image
    print("\n4. Web and admin: names the code reads that production leaves to a default")
    for svc, reads in (("web", web_reads), ("admin", admin_reads)):
        env = prod.get(svc, {})
        for name, at in sorted(reads.items()):
            if name in env or name == "NODE_ENV":
                continue
            src = derived.get(name)
            if src and src in env:
                continue
            how = "the image's build-arg default" if (name in args or (src and src in args)) else "the code's fallback"
            print(f"  {svc}: {name} uses {how} ({at})")

    # 5. Backend settings production leaves at their default (count only; see the doc for the ones that matter)
    every = {n for env in (prod.get(s, {}) for s in BACKENDS) for n in env}
    defaults = sorted(set(fields) - every)
    print(f"\n5. Backend settings production leaves at their config.py default: {len(defaults)} of {len(fields)}")
    unknown_env = sorted(set(env_reads) - set(fields) - every - {"RAILWAY_ENVIRONMENT_NAME"})
    if unknown_env:
        print("  direct os.environ reads with defaults: " + ", ".join(unknown_env))
    unused = sorted(n for s in BACKENDS for n in prod.get(s, {}) if n not in fields and n not in env_reads)
    if unused:
        print("  defined for production but not read as a setting (build args or image settings): "
              + ", ".join(sorted(set(unused))))

    # 6. The three app builds (outside Railway)
    print("\n6. App builds (customer, partner, rider): build-time names, set outside Railway")
    print("  read by the apps: " + ", ".join(expo_names))
    profile = (ROOT / "tools/mobile/env-profile.sh").read_text(encoding="utf-8")
    profiles = re.findall(r"^\s{2}(\w+)\)", profile, re.M)
    if "production" not in profiles:
        gaps.append("apps: no production profile")
        print(f"  GAP  tools/mobile/env-profile.sh has profiles {', '.join(profiles)}; none for production "
              f"({line_of('tools/mobile/env-profile.sh', 'case')})")
    for app in ("customer", "partner", "rider"):
        cfg = json.loads((ROOT / f"apps/{app}/app.json").read_text(encoding="utf-8"))["expo"]
        pid = cfg.get("extra", {}).get("eas", {}).get("projectId", "")
        if not (ROOT / f"apps/{app}/eas.json").exists():
            gaps.append(f"{app}: no eas.json")
            print(f"  GAP  apps/{app}: no eas.json (no store build profile)")
        if not pid or pid.startswith("your-"):
            gaps.append(f"{app}: EAS projectId placeholder")
            print(f"  GAP  apps/{app}: EAS projectId is a placeholder ({line_of(f'apps/{app}/app.json', 'projectId')})")
        gsf = cfg.get("android", {}).get("googleServicesFile")
        if gsf and not (ROOT / f"apps/{app}" / gsf).exists():
            print(f"  note apps/{app}: {gsf} is not in the checkout (Firebase; app.config.js drops it, so no FCM)")

    print(f"\nResult: {len(gaps)} gap(s), {warn} warning(s).")
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
