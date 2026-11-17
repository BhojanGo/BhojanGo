// node --test: Partners -> Applications lists the documents from the kitchen's
// country in Markets (kitchen_documents), with the names admins gave them.
import assert from "node:assert/strict";
import test from "node:test";

import { applicationDocs, collected, marketDocs } from "../src/lib/kitchenDocs.ts";

const doc = (key: string, en: string, extra: Record<string, string> = {}) => ({ key, title: { en, ...extra }, why: { en: "Because." } });
const INDIA = { kitchen_documents: [doc("fssai", "FSSAI licence", { hi: "FSSAI लाइसेंस" }), doc("gstin", "GST registration (GSTIN)"), doc("pan", "PAN"), doc("bank", "Bank account")] };
const US = { kitchen_documents: [doc("health_permit", "Food establishment or health permit"), doc("ein", "EIN"), doc("bank", "Bank account")] };
const EMPTY_APP = { fssai_number: null, fssai_expires_on: null, fssai_document_key: null, gstin: null, payout_account: null };
const FULL_APP = { fssai_number: "12345678901234", fssai_expires_on: "2027-03-31", fssai_document_key: "docs/x.pdf", gstin: "36AAAAA0000A1Z5", payout_account: "active" };

test("the list, its order and its English names come from Markets", () => {
  assert.deepEqual(marketDocs(INDIA).map((d) => d.label), ["FSSAI licence", "GST registration (GSTIN)", "PAN", "Bank account"]);
  assert.deepEqual(marketDocs(US).map((d) => d.key), ["health_permit", "ein", "bank"]);
  assert.deepEqual(marketDocs({}), []);
  assert.deepEqual(marketDocs(null), []);
  assert.deepEqual(marketDocs({ kitchen_documents: [{ key: "x" }, "junk", doc("ok", "OK")] }), [{ key: "ok", label: "OK" }]);
});

test("each document shows what the kitchen saved for it", () => {
  const rows = applicationDocs(FULL_APP, INDIA);
  assert.deepEqual(rows.map((r) => [r.label, r.value]), [
    ["FSSAI licence", "12345678901234 · until 2027-03-31"],
    ["GST registration (GSTIN)", "36AAAAA0000A1Z5"],
    ["PAN", null],
    ["Bank account", "active"],
  ]);
  assert.equal(rows[0]!.fileKey, "docs/x.pdf");
  assert.equal(collected("pan"), false);
  assert.equal(collected("gstin"), true);
});

test("a country with other documents shows its own names, nothing from India", () => {
  const rows = applicationDocs(EMPTY_APP, US);
  assert.deepEqual(rows.map((r) => r.label), ["Food establishment or health permit", "EIN", "Bank account"]);
  assert.ok(rows.every((r) => r.value === null));
  assert.ok(!rows.some((r) => /FSSAI|GST/.test(r.label)));
});

test("nothing saved is hidden when Markets doesn't list it; the payout account always shows", () => {
  const rows = applicationDocs(FULL_APP, {});
  assert.deepEqual(rows.map((r) => [r.label, r.value]), [
    ["Food licence", "12345678901234 · until 2027-03-31"],
    ["Tax registration", "36AAAAA0000A1Z5"],
    ["Payout account", "active"],
  ]);
  assert.deepEqual(applicationDocs(EMPTY_APP, undefined).map((r) => r.label), ["Payout account"]);
});
