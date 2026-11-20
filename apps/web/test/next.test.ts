// node --test: where sign-in sends you next stays on this site (R21 security review).
import assert from "node:assert/strict";
import test from "node:test";

import { safeNext } from "../src/app/signin/next.ts";

const TAB = String.fromCharCode(9);
const NEWLINE = String.fromCharCode(10);
const BACKSLASH = String.fromCharCode(92);

test("paths on this site are kept", () => {
  assert.equal(safeNext("/checkout"), "/checkout");
  assert.equal(safeNext("/in/hyderabad?x=1#menu"), "/in/hyderabad?x=1#menu");
  assert.equal(safeNext(null), "/");
});

test("other sites are refused, however they're spelled", () => {
  const bad = ["//evil.com", `/${BACKSLASH}evil.com`, "https://evil.com", `/${TAB}/evil.com`, `/${NEWLINE}/evil.com`,
    `${TAB}//evil.com`, "javascript:alert(1)", "evil.com"];
  for (const b of bad) assert.equal(safeNext(b), "/", JSON.stringify(b));
});
