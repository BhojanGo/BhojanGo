// node --test: R22 security review, S8. The console's session is in httpOnly cookies that
// core_api sets through the console's /api rewrites: no token is kept in the page's storage
// or sent from script, so an XSS can't read one. (The Playwright run also checks localStorage
// after a real sign-in with the second step.)
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

const SRC = join(import.meta.dirname, "..", "src");
const read = (...p: string[]) => readFileSync(join(SRC, ...p), "utf8");

test("the auth store keeps no token", () => {
  const store = read("store", "auth.ts");
  assert.doesNotMatch(store, /accessToken|refreshToken|access_token|refresh_token/, "the persisted store holds a token");
  assert.match(store, /partialize: \(s\) => \(\{ user: s\.user, isAuthenticated: s\.isAuthenticated \}\)/);
  assert.match(store, /localStorage\.removeItem\("bhojango-admin-auth"\)/, "old sessions' tokens must be removed");
});

test("calls carry the cookie session, never a bearer token", () => {
  const api = read("lib", "api.ts");
  assert.match(api, /"X-Session": "admin"/);
  assert.match(api, /withCredentials: true/);
  assert.doesNotMatch(api, /Authorization|Bearer|refresh_token/);
});

test("the sign-in page hands the store only the user", () => {
  const login = read("app", "login", "page.tsx");
  assert.doesNotMatch(login, /login\(tokens\.access_token/);
  assert.match(login, /login\(tokens\.user\)/);
});
