// node --test: Account -> Legal links and the words when the server keeps an account (R19).
import assert from "node:assert/strict";
import test from "node:test";

import { deleteAccountProblem, legalPageUrl } from "../src/account-text.ts";

const t = (key: string, vars?: Record<string, string | number>) =>
  vars ? `${key}(${Object.entries(vars).map(([k, v]) => `${k}=${v}`).join(",")})` : key;

test("legal pages are the website's, for the account's country", () => {
  assert.equal(legalPageUrl("https://example.test/", "privacy", "US"), "https://example.test/privacy?country=US");
  assert.equal(legalPageUrl("https://example.test", "terms", null), "https://example.test/terms");
});

test("money still owed says how much; orders in progress say to finish them; the rest: try again", () => {
  const owed = { status: 409, code: "MONEY_OWED", body: { detail: { code: "MONEY_OWED", amount: "$12.50" } } };
  assert.equal(deleteAccountProblem(owed, t), "account.delete.money_owed(amount=$12.50)");
  assert.equal(deleteAccountProblem({ status: 409, body: { detail: { code: "ORDERS_IN_PROGRESS" } } }, t), "account.delete.orders_in_progress");
  assert.equal(deleteAccountProblem({ status: 500 }, t), "account.privacy.failed");
  assert.equal(deleteAccountProblem(new TypeError("Network request failed"), t), "account.privacy.failed");
});
