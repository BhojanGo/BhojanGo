// node --test: R22 security review, S9. The pages' Content-Security-Policy runs only scripts that
// carry the page's nonce: never script-src 'unsafe-inline', so an injected inline script is refused.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const headers = require("../security-headers");

const ROOT = path.join(__dirname, "..", "..", "..");
const scriptSrc = (csp) => csp.split(";").map((d) => d.trim()).find((d) => d.startsWith("script-src")) ?? "";

function inProduction(fn) {
  const was = process.env.NODE_ENV;
  process.env.NODE_ENV = "production";
  try {
    return fn();
  } finally {
    process.env.NODE_ENV = was;
  }
}

test("a page's script-src is its nonce and 'strict-dynamic', never 'unsafe-inline'", () => {
  assert.equal(typeof headers.contentSecurityPolicy, "function", "no per-page CSP");
  const csp = inProduction(() => headers.contentSecurityPolicy({ script: ["https://js.stripe.com"] }, "abc123=="));
  const script = scriptSrc(csp);
  assert.match(script, /'nonce-abc123=='/);
  assert.match(script, /'strict-dynamic'/);
  assert.doesNotMatch(script, /unsafe-inline/);
  assert.doesNotMatch(script, /unsafe-eval/);
  assert.match(csp, /object-src 'none'/);
  assert.match(csp, /frame-ancestors 'none'/);
  assert.match(csp, /base-uri 'self'/);
});

test("without a nonce scripts come from our origin only", () => {
  const script = scriptSrc(inProduction(() => headers.contentSecurityPolicy({})));
  assert.doesNotMatch(script, /unsafe-inline|nonce-/);
});

test("the fixed headers (next.config) carry no CSP that allows inline script", () => {
  const all = inProduction(() => headers.securityHeaders({ img: ["https:"], script: ["https://js.stripe.com"] }));
  for (const h of all) {
    if (h.key.toLowerCase() === "content-security-policy") assert.doesNotMatch(scriptSrc(h.value), /unsafe-inline/, h.value);
  }
  assert.ok(all.some((h) => h.key === "X-Frame-Options"));
});

test("each nonce is new and long enough", () => {
  const seen = new Set(Array.from({ length: 50 }, () => headers.newNonce()));
  assert.equal(seen.size, 50);
  for (const n of seen) assert.ok(Buffer.from(n, "base64").length >= 16, n);
});

test("both apps send the per-page CSP from their proxy", () => {
  for (const app of ["web", "admin"]) {
    const proxy = fs.readFileSync(path.join(ROOT, "apps", app, "src", "proxy.ts"), "utf8");
    assert.match(proxy, /contentSecurityPolicy\(/, `${app}: proxy.ts doesn't build the CSP`);
    assert.match(proxy, /response\.headers\.set\("Content-Security-Policy"/, `${app}: the CSP isn't on the response`);
    assert.match(proxy, /headers\.set\("Content-Security-Policy"/, `${app}: Next can't see the nonce`);
  }
});
