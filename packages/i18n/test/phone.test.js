// node --test: phone numbers for people to read (R22), the one formatter for web, admin and the apps.
const test = require("node:test");
const assert = require("node:assert/strict");
const { formatPhone } = require("..");

test("United States and Canada: +1 208-555-0291", () => {
  assert.equal(formatPhone("+12085550291"), "+1 208-555-0291");
  assert.equal(formatPhone("+14165550123"), "+1 416-555-0123");
});

test("India: +91 98765 43210 (five and five)", () => {
  assert.equal(formatPhone("+919876543210"), "+91 98765 43210");
  assert.equal(formatPhone("+919000000101"), "+91 90000 00101");
});

test("the other countries in the table", () => {
  assert.equal(formatPhone("+447700900123"), "+44 7700 900123");
  assert.equal(formatPhone("+442079460958"), "+44 20 7946 0958");
  assert.equal(formatPhone("+61412345678"), "+61 412 345 678");
  assert.equal(formatPhone("+61298765432"), "+61 2 9876 5432");
  assert.equal(formatPhone("+64211234567"), "+64 21 123 4567");
  assert.equal(formatPhone("+6491234567"), "+64 9 123 4567");
  assert.equal(formatPhone("+6581234567"), "+65 8123 4567");
  assert.equal(formatPhone("+971501234567"), "+971 50 123 4567");
  assert.equal(formatPhone("+97141234567"), "+971 4 123 4567");
});

test("already formatted numbers keep (or get) the same format", () => {
  assert.equal(formatPhone("+1 208-555-0291"), "+1 208-555-0291");
  assert.equal(formatPhone("+1 (208) 555-0291"), "+1 208-555-0291");
  assert.equal(formatPhone("+91 98765 43210"), "+91 98765 43210");
  assert.equal(formatPhone("+91 9876 543 210"), "+91 98765 43210");
  assert.equal(formatPhone(" +12085550291 "), "+1 208-555-0291");
  assert.equal(formatPhone(formatPhone("+919876543210")), "+91 98765 43210");
});

test("too short or too long for the country: unchanged", () => {
  assert.equal(formatPhone("+1208555029"), "+1208555029");
  assert.equal(formatPhone("+120855502911"), "+120855502911");
  assert.equal(formatPhone("+9198765"), "+9198765");
  assert.equal(formatPhone("+91"), "+91");
  assert.equal(formatPhone("+"), "+");
});

test("missing plus: unchanged (no guessing the country)", () => {
  assert.equal(formatPhone("2085550291"), "2085550291");
  assert.equal(formatPhone("919876543210"), "919876543210");
  assert.equal(formatPhone("98765 43210"), "98765 43210");
});

test("unknown country code: unchanged", () => {
  assert.equal(formatPhone("+33612345678"), "+33612345678");
  assert.equal(formatPhone("+998123456789"), "+998123456789");
  assert.equal(formatPhone("+0123456789"), "+0123456789");
});

test("not a phone number: unchanged, never throws, no digit dropped", () => {
  assert.equal(formatPhone("not a phone"), "not a phone");
  assert.equal(formatPhone("+1 208 555 0291 ext 4"), "+1 208 555 0291 ext 4");
  assert.equal(formatPhone("112"), "112");
  assert.equal(formatPhone(null), "");
  assert.equal(formatPhone(undefined), "");
  assert.equal(formatPhone(""), "");
  assert.equal(formatPhone(12085550291), "12085550291");
  assert.doesNotThrow(() => formatPhone({ toString() { throw new Error("x"); } }));
  for (const n of ["+12085550291", "+919876543210", "+447700900123", "+971501234567"]) {
    assert.equal(formatPhone(n).replace(/\D/g, ""), n.replace(/\D/g, ""));
  }
});
