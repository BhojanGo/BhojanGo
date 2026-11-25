// node --test: R38 phone numbers by country (phone.js, libphonenumber-js).
import assert from "node:assert/strict";
import test from "node:test";

import { callingCode, formatAsYouType, formatPhone, isValidPhone, parsePhone, phoneExample, phonePlaceholder, reformatPhone, toE164, typePhone } from "../phone.js";

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

/** Types the digits one by one into a box (as a person does), returning what the box shows after each. */
function typeEach(digits, country, start = "") {
  const shown = [];
  let box = start;
  for (const d of digits) {
    box = typePhone(box, box + d, country);
    shown.push(box);
  }
  return shown;
}

test("R39: US digits one by one follow the US grouping", () => {
  assert.deepEqual(typeEach("2085550123", "US"), [
    "2", "20", "(208)", "(208) 5", "(208) 55", "(208) 555", "(208) 555-0", "(208) 555-01", "(208) 555-012", "(208) 555-0123"]);
});

test("R39: India digits one by one follow the Indian grouping", () => {
  assert.deepEqual(typeEach("9876543210", "IN"), [
    "9", "98", "987", "9876", "98765", "98765 4", "98765 43", "98765 432", "98765 4321", "98765 43210"]);
});

test("R39: backspace over a formatting character deletes the digit before it", () => {
  assert.equal(typePhone("(208)", "(208", "US"), "20");
  assert.equal(typePhone("(208) 5", "(208) ", "US"), "(208)");
  assert.equal(typePhone("98765 4", "98765 ", "IN"), "98765");
  assert.equal(typePhone("98765 43210", "", "IN"), "");
});

test("R39: switching the country re-formats what is typed", () => {
  assert.equal(reformatPhone("(987) 654-3210", "IN"), "98765 43210");
  assert.equal(reformatPhone("98765 43210", "US"), "(987) 654-3210");
  assert.equal(reformatPhone("20 8555 0123", "US"), "(208) 555-0123");
  assert.equal(reformatPhone("", "US"), "");
});

test("R39: a + number keeps its own country's grouping; pasted text is cleaned; 15 digits at most", () => {
  assert.equal(typePhone("", "+447911123456", "US"), "+44 7911 123456");
  assert.equal(typePhone("", "+", "IN"), "+");
  assert.equal(typePhone("", "tel: 208-555-0123", "US"), "(208) 555-0123");
  assert.equal(typePhone("", "1234567890123456789", "US").replace(/\D/g, "").length, 15);
});
