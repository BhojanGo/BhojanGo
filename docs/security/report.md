# Security report: automated testing in place of the pen test

**Date:** 2026-11-12
**Scope:** core_api, realtime and worker (APIs), the customer web, the admin console, their container images,
dependencies, infrastructure code and the full git history.

The tracker's item is "an outside pen test; all high issues fixed". We ran the zero-spend version instead: the same
classes of check with free tools, against `make dev`. **Every High and Critical finding with a fix has been fixed.**
The rest are triaged below; none is exploitable in how we run.

This doesn't replace a human penetration test. Automated scanners don't find business-logic flaws (pricing,
refunds, scoping). Those are covered by our own access sweep (`test_zz_access_sweep.py`), which runs every endpoint
three ways: no token, the wrong role, and someone else's resource. Book an outside test before public launch.

## Summary

| Check | Tool | Before | After |
|---|---|---|---|
| Web app scan, API | OWASP ZAP API scan (OpenAPI, active) | 0 High · 2 Low | **0 High · 0 Medium** · 1 Low (119 passed) |
| Web app scan, customer web | OWASP ZAP full scan (spider + active) | 0 High · 2 Medium · 6 Low | **0 High** · 3 Medium (CSP strength) · 1 Low (141 passed) |
| Web app scan, admin | OWASP ZAP full scan | 0 High · 2 Medium · 7 Low | **0 High** · 2 Medium (CSP strength) · 2 Low (140 passed) |
| Code | semgrep (default, python, typescript, secrets rules) | 26 ERROR | **8 ERROR, all triaged false positives or accepted** |
| Secrets in all commits | gitleaks (full history) | 0 leaks *(wrong: no rules were active, see below)* | **55 findings, all dead; reviewed and listed in `.gitleaksignore`; 0 new** |
| Python dependencies (129) | pip-audit | 2 (ecdsa High, python-jose) | **0** |
| JavaScript dependencies | pnpm audit | 1 Critical · 70 High · 49 Moderate · 14 Low | **0 Critical · 0 High** · 7 Moderate · 5 Low |
| Container images (5) | trivy image (HIGH, CRITICAL) | 2–6 fixable each, 1 Critical (web, admin) | **0 fixable, 0 Critical**; unfixed Debian base packages remain (below) |
| Dockerfiles, Terraform | trivy config | images ran as root (High), 7 IaC issues | **app images non-root**; IaC fixes below |

## What we fixed

**Application**
- **Security headers (ZAP, Medium/Low).**
  - Web and admin now send a Content-Security-Policy (`frame-ancestors 'none'`, `object-src 'none'`, connect only to
    our APIs, frames only for the payment providers), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
    `Referrer-Policy`, `Permissions-Policy` (camera and microphone off; location only on the web, for "use my
    location"), COOP and CORP.
  - They no longer send `X-Powered-By` (`packages/ui/security-headers.js`).
  - All three APIs send `nosniff`, CORP `same-site`, `X-Frame-Options: DENY` and `Referrer-Policy: no-referrer`
    (`backend/shared/middleware/security.py`, tested).
- **Shell injection in the deploy workflow (semgrep).** Workflow inputs were pasted into shell scripts
  (`${{ inputs.environment }}`). They now reach the scripts as environment variables (`deploy.yml`, `pr-checks.yml`).
- **Test tokens in a committed file (semgrep).** The k6 summary from P24 included setup data: access tokens of seed
  test accounts. They were signed by a throwaway local development key and expired 15 minutes after the run, so they
  aren't usable anywhere. They're removed from the file, and `tools/load/run.sh` strips them from every future
  summary. They remain in the history of #45; rewriting public history isn't worth it for dead dev tokens.

**Dependencies**
- **python-jose and ecdsa (pip-audit).** python-jose had an unfixed CVE and pulled in ecdsa (CVE-2024-23342,
  timing side channel, High). Nothing imported python-jose; the code uses PyJWT. Removed.
- **pnpm (1 Critical, 70 High → 0).**
  - axios in admin went from 1.7 to 1.20, which covers 11 advisories: prototype pollution, credential leaks and ReDoS.
  - Patched versions of transitive packages are pinned with `pnpm.overrides`, each within its own major line:
    shell-quote (Critical), @xmldom/xmldom, glob, minimatch, brace-expansion, js-yaml, ws, form-data, node-forge,
    nanoid, postcss, browserslist, compression, decode-uri-component, joi, source-map-js and zod.
  - Most of these were in the Expo/React Native and ESLint build tools, not in what customers run.

**Containers**
- **Non-root (trivy DS002, High).**
  - core_api, realtime and worker run as an unprivileged `app` user (uid 10001).
  - Web, admin and batch-engine run as `node`.
  - For existing local volumes, `make dev` hands the JWT dev-key volume over once (`keys-init`).
- **Base images.** Debian security updates are applied at build time; this fixed zlib (2 High) in the Python images.
- **Node images.**
  - They moved to Debian 13 (`node:24-trixie-slim`), clearing the Critical zlib/minizip CVE-2023-45853.
  - The runtime image no longer ships npm, whose bundled undici and brace-expansion carried 6 High CVEs. Next is
    started directly.

**Infrastructure code** (Terraform, not deployed: zero spend)
- Assets and logs buckets are encrypted at rest (SSE-S3).
- The SNS alerts topic is encrypted (AWS-managed key).
- Load balancer egress is limited to the services' security group, instead of anywhere.

## Accepted, with reasons

| Finding | Severity | Why it stays |
|---|---|---|
| Debian 13 base packages with no fix yet (util-linux, ncurses, systemd libs, sqlite, gzip), about 46 High per image, 0 Critical | High | No fixed version exists upstream. None is used by the running services (no login, mount or shell tools are called), and the containers run as non-root. Images rebuild on every deploy and pick up fixes as Debian ships them. Re-scan with trivy weekly. |
| CSP `script-src 'unsafe-inline'`, `style-src 'unsafe-inline'`; `img-src https:` (web) | Medium (ZAP) | Next.js renders inline bootstrap scripts and our JSON-LD. Removing `unsafe-inline` needs per-request nonces, which would make every page dynamic and lose the cached city and kitchen pages. Kitchen photos come from S3/CloudFront. Next step: nonce-based CSP once page caching moves to the CDN. |
| Cross-Origin-Embedder-Policy missing (web, admin) | Low | `require-corp` would block the map tiles and kitchen photos, which come from other origins. |
| API CORP `same-site` instead of `same-origin` | Low | The web app calls the API from another origin of the same site. |
| Admin "big redirect" | Low | The admin's sign-in redirect body. It contains no data. |
| semgrep "credentials in URI" (Makefile), "raw SQL" (migration 0003), "insecure websocket" (realtime docstring), "GCM service account" (worker FCM) | ERROR | False positives: `localhost:$${PORT}`, a constant extension list, an example URL in a docstring, and a key read from settings. |
| semgrep / trivy: test image runs as root (`infra/docker/test.Dockerfile`) | High | CI-only image, never deployed. |
| GitHub Actions use version tags, not commit SHAs (40) | Warning | Official actions (actions/*, docker/*, aws-actions/*). Pin by SHA when Dependabot is turned on. |
| Terraform: public load balancer and public subnets, unrestricted egress for ECS tasks, HTTP listener without a certificate on a first staging deploy, mutable ECR tags, no WAF, no customer-managed KMS keys | High/Critical (trivy) | The load balancer is meant to be public. Tasks must reach Stripe, Razorpay, Twilio and MSG91. HTTP redirects to HTTPS as soon as a certificate is set. The deploy pushes a moving `-latest` tag (scan-on-push is on). WAF and customer-managed KMS keys cost money and are not needed for the pilot. Revisit before production traffic. |
| pnpm audit: 7 Moderate, 5 Low | Moderate/Low | Below the bar for this pass; all in build tooling. Dependabot will pick them up. |

## Signing keys and tokens in git history (follow-up, 2026-11-12)

### The local dev signing key

Access and refresh tokens are RS256, signed only by core_api (`backend/shared/jwt_keys.py`).

- **Generated per machine.** With no `JWT_PRIVATE_KEY` set, core_api generates a fresh 2048-bit RSA key the first
  time it starts (`rsa.generate_private_key`) and keeps it at `JWT_DEV_KEY_PATH`. Under `make dev` that is the
  Docker volume `jwt_keys` on that machine. Each developer's machine, each CI run and each throwaway stack (G1, the
  backup drill) has its own key. `make reset` (or `down -v`) deletes it and the next start makes a new one.
- **Never in git.** No key file, PEM or key material is committed; gitleaks's private-key rule checks every commit.
  The key's id (`kid`) is a thumbprint of the public key, so a token from one machine is rejected by every other one.
- **Never used in any other environment.** A dev key is only made when `APP_ENV` is `development` or `test`.
  Anywhere else (staging, production, a preview, any other value), core_api refuses to start without
  `JWT_PRIVATE_KEY`; verification-only services (realtime, worker) only trust core_api's JWKS. Tested:
  `test_dev_key_only_in_development_and_test`. Before this follow-up, the check was "not production", so a staging
  deploy with a missing secret would have quietly generated its own key. It now fails at start instead.
- **Production keys** come from the platform's secret store (Secrets Manager on AWS, a sealed variable on Railway);
  rotation is documented in `jwt_keys.py` (`JWT_PUBLIC_KEYS` keeps accepting the old key during the change-over).

### What the full-history scan found

The first pass reported "0 leaks", but that number was wrong. Our `.gitleaks.toml` had an empty `[extend]` section,
which turns the default rules **off**, so gitleaks was checking every commit against no rules. With the defaults on
(`useDefault = true`) and our own JWT rule, the full history has 55 findings in 3 places. All are dead:

| Where (history only) | What | Why it can't be used |
|---|---|---|
| `docs/load/summary-2026-11-12.json` (#45) | 26 access tokens of seed test accounts (each found by two rules) | RS256, signed by the throwaway dev key of the machine that ran k6; expired 15 minutes after the run; that key exists nowhere else. Removed from the file in #46 |
| `apps/web/e2e/.auth/customer-state.json` (June 2026, since deleted) | A Playwright login state: one access, one refresh token | HS256 with the old public dev secret. HS256 was retired in P5: every service accepts only RS256 with a known `kid` (`test_forged_and_downgraded_tokens_are_rejected`). Expired June 2026 |
| `docker-compose.yml` (April 2026, since deleted) | `STRIPE_SECRET_KEY: sk_test_placeholder` | A placeholder, not a key |

We didn't rewrite history (your decision): these findings are recorded by fingerprint in `.gitleaksignore`, so the
scan only fails on something new. Never add a live secret to that file; rotate it instead.

### Stopping it happening again

- **gitleaks rule `bhojango-jwt`** (`.gitleaks.toml`): any `eyJ….eyJ….…` token in any file, docs included. The
  default rules are back on. CI runs gitleaks over every commit on each pull request (`security.yml`) and in
  `make ci` (`ci-secrets`), with `--redact` so a finding never lands in a log.
- **Pre-commit hook** (`.husky/pre-commit` → `tools/git-hooks/no-jwt.sh`): blocks a commit whose staged lines add a
  JWT and prints the file with the token masked. `pnpm install` installs it (husky). It has no bypass list on
  purpose; `--no-verify` skips it, and CI still catches it.
- `tools/load/run.sh` strips setup data (tokens) from k6 summaries (#46).

## How to rerun

All of these run in Docker against `make dev` (`COMPOSE_PROJECT_NAME`/network `bhojango_default`):

```sh
# Web scans
docker run --rm --network bhojango_default -v "$PWD/out:/zap/wrk" ghcr.io/zaproxy/zaproxy:stable \
  zap-api-scan.py -t http://core-api:8001/openapi.json -f openapi -J zap-api.json -I
docker run --rm --network bhojango_default -v "$PWD/out:/zap/wrk" ghcr.io/zaproxy/zaproxy:stable \
  zap-full-scan.py -t http://web:3000 -J zap-web.json -m 5 -I        # and http://admin:3000

# Code, secrets, dependencies, images
docker run --rm -v "$PWD:/src" -w /src semgrep/semgrep:1.113.0 semgrep scan --config p/default --config p/python --config p/typescript --config p/secrets
docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:v8.21.2 git /repo --config /repo/.gitleaks.toml --gitleaks-ignore-path /repo/.gitleaksignore --redact   # also in make ci
(cd backend && uv export --frozen --no-hashes --no-emit-project -o /tmp/req.txt && uv tool run pip-audit -r /tmp/req.txt --no-deps --disable-pip)
NODE_OPTIONS=--max-old-space-size=8192 pnpm audit
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:0.61.0 image --severity HIGH,CRITICAL bhojango-core-api   # each image
docker run --rm -v "$PWD:/src" aquasec/trivy:0.61.0 config --severity HIGH,CRITICAL /src
```

GitHub already runs Semgrep, Bandit, a dependency audit and secret detection on every pull request (`security.yml`).
