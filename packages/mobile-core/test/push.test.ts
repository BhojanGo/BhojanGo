// node --test: R19 push registration's pure rules (src/push-config.ts).
import assert from "node:assert/strict";
import test from "node:test";

import { easProjectId, pushPlatform } from "../src/push-config.ts";

test("only a real EAS project id (a UUID) registers; placeholders skip quietly", () => {
  assert.equal(easProjectId("0b6c2f4e-8f1a-4c4e-9a52-3c1f0d2b7e91"), "0b6c2f4e-8f1a-4c4e-9a52-3c1f0d2b7e91");
  assert.equal(easProjectId(" 0B6C2F4E-8F1A-4C4E-9A52-3C1F0D2B7E91 "), "0B6C2F4E-8F1A-4C4E-9A52-3C1F0D2B7E91");
  assert.equal(easProjectId("your-eas-project-id"), null);
  assert.equal(easProjectId("REPLACE_ME_EAS_PROJECT_ID_CUSTOMER"), null);
  assert.equal(easProjectId(""), null);
  assert.equal(easProjectId(undefined), null);
  assert.equal(easProjectId(42), null);
});

test("phones only: iOS and Android", () => {
  assert.equal(pushPlatform("ios"), "ios");
  assert.equal(pushPlatform("android"), "android");
  assert.equal(pushPlatform("web"), null);
});
