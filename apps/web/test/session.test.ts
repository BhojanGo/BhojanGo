// node --test: R22 security review, S8. The website's session is in httpOnly cookies that
// core_api sets: no token is kept in the page's storage or sent from script, so an XSS
// can't read one. (The Playwright run also checks localStorage after a real sign-in.)
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

const SRC = join(import.meta.dirname, "..", "src");

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? files(p) : /\.(ts|tsx)$/.test(n) ? [p] : [];
  });
}

test("the session store keeps no token", () => {
  const client = readFileSync(join(SRC, "lib", "client.ts"), "utf8");
  const store = client.slice(client.indexOf("export const useSession"), client.indexOf("export const api"));
  assert.ok(store.length > 0, "no session store");
  assert.doesNotMatch(store, /refreshToken|access_token|refresh_token|\baccess:/, "the persisted session holds a token");
  assert.match(store, /partialize: \(s\) => \(\{ signedIn: s\.signedIn, user: s\.user \}\)/, "the store must persist only who is signed in");
  assert.match(client, /localStorage\.removeItem\("bhojango-session"\)/, "old sessions' tokens must be removed");
});

test("every call to core_api carries the cookies and says it's the website", () => {
  const client = readFileSync(join(SRC, "lib", "client.ts"), "utf8");
  assert.match(client, /credentials: "include"/);
  assert.match(client, /"X-Session", "web"/);
  assert.match(client, /session: "web"/, "the typed client must use the cookie session");
});

test("no page sends a token of its own", () => {
  const offenders = files(SRC).filter((f) => /authorization:\s*`Bearer|Authorization:\s*`Bearer|\.access\b/.test(readFileSync(f, "utf8")));
  assert.deepEqual(offenders, []);
});
