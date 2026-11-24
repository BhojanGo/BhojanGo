// node --test: R38 phone numbers by country (phone.js, libphonenumber-js).
import assert from "node:assert/strict";
import test from "node:test";

import { callingCode, formatAsYouType, formatPhone, isValidPhone, parsePhone, phoneExample, phonePlaceholder, toE164 } from "../phone.js";

test("valid US and India numbers, typed the country's way, become E.164", () => {
  assert.equal(toE164("(208) 555-0123", "US"), "+12085550123");
  assert.equal(toE164("208-555-0123", "US"), "+12085550123");
  assert.equal(toE164("98765 43210", "IN"), "+919876543210");
  assert.equal(toE164("098765 43210", "IN"), "+919876543210");  // a leading 0 (trunk prefix)
  assert.equal(toE164("+91 98765 43210", "US"), "+919876543210");  // an international number keeps its country
});

test("invalid numbers are refused", () => {
  for (const [n, c] of [["12345", "US"], ["555-0123", "US"], ["(000) 555-0123", "US"], ["00000 00000", "IN"], ["+91 12345", "US"], ["98765", "IN"], ["", "IN"], ["abc", "US"]]) {
    assert.equal(isValidPhone(n, c), false, `${n} in ${c}`);
  }
});

test("a US number for an India address is fine when it is a real number (international allowed)", () => {
  assert.deepEqual(parsePhone("+12085550123", "IN"), { e164: "+12085550123", valid: true, country: "US" });
});

test("display: US +1 (208) 555-0123, India +91 98765 43210", () => {
  assert.equal(formatPhone("+12085550123"), "+1 (208) 555-0123");
  assert.equal(formatPhone("+919876543210"), "+91 98765 43210");
  assert.equal(formatPhone("not a number"), "not a number");
});

test("placeholders and examples follow the country: no Indian example for the US, no US one for India", () => {
  assert.equal(callingCode("US"), "+1");
  assert.equal(callingCode("IN"), "+91");
  assert.equal(phonePlaceholder("US"), "(208) 555-0123");
  assert.equal(phonePlaceholder("IN"), "98765 43210");
  assert.equal(phoneExample("US"), "+1 (208) 555-0123");
  assert.equal(phoneExample("IN"), "+91 98765 43210");
  assert.ok(!phonePlaceholder("US").includes("98765") && !phoneExample("US").includes("+91"));
  assert.ok(!phoneExample("IN").includes("+1 ") && !phonePlaceholder("IN").includes("("));
  assert.ok(phoneExample("GB").startsWith("+44"));  // another market: libphonenumber's example
});

test("formatting as you type", () => {
  assert.equal(formatAsYouType("2085550123", "US"), "(208) 555-0123");
  assert.equal(formatAsYouType("9876543210", "IN"), "98765 43210");
});
