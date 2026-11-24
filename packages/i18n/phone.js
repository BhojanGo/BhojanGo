// R38: phone numbers by country, shared by the website, the admin console and the apps (libphonenumber-js;
// R22's hand-written table is gone: the brief asks for libphonenumber and "+1 (208) 555-0123" for the US).
// Parse what a person types in their country's way (or with a "+" and another country's code), check it
// is a real number, keep E.164 only (+12085550123), and show it the country's way:
//   US (and the rest of +1): "+1 (208) 555-0123"; India and others: "+91 98765 43210".
// Placeholders and examples follow the country, so a US user never sees an Indian example.
const { parsePhoneNumberFromString, AsYouType, getCountryCallingCode, getExampleNumber } = require("libphonenumber-js/min");
const EXAMPLES_ALL = require("libphonenumber-js/mobile/examples");

// Our own examples where we operate (Boise's area code; an Indian mobile).
const EXAMPLES = { US: "+12085550123", IN: "+919876543210" };

function upper(country) {
  return typeof country === "string" && /^[A-Za-z]{2}$/.test(country) ? country.toUpperCase() : undefined;
}

/** {e164, valid, country} for what was typed in ``country`` (a "+" number keeps its own country); null when it can't be read. */
function parsePhone(input, country) {
  const text = String(input ?? "").trim();
  if (!/\d/.test(text)) return null;
  const p = parsePhoneNumberFromString(text, upper(country));
  if (!p) return null;
  return { e164: p.number, valid: p.isValid(), country: p.country ?? null };
}

/** E.164 for a valid number, else null. */
function toE164(input, country) {
  const p = parsePhone(input, country);
  return p && p.valid ? p.e164 : null;
}

function isValidPhone(input, country) {
  return toE164(input, country) !== null;
}

/** How a stored number is shown: "+1 (208) 555-0123", "+91 98765 43210"; as given when it can't be read. */
function formatPhone(e164) {
  if (!e164) return "";
  const p = parsePhoneNumberFromString(String(e164).trim());
  if (!p) return String(e164);
  if (p.countryCallingCode === "1") return `+1 ${p.formatNational()}`;
  return p.formatInternational();
}

/** The country's calling code: "+1", "+91". */
function callingCode(country) {
  const c = upper(country);
  try {
    return c ? `+${getCountryCallingCode(c)}` : "";
  } catch {
    return "";
  }
}

function example(country) {
  const c = upper(country);
  if (!c) return null;
  if (EXAMPLES[c]) return parsePhoneNumberFromString(EXAMPLES[c]);
  try {
    return getExampleNumber(c, EXAMPLES_ALL) ?? null;
  } catch {
    return null;
  }
}

/** The placeholder after the country-code box, as typed there: "(208) 555-0123", "98765 43210". */
function phonePlaceholder(country) {
  const e = example(country);
  return e ? new AsYouType(upper(country)).input(String(e.nationalNumber)) : "";
}

/** A whole example for help text: "+1 (208) 555-0123", "+91 98765 43210". */
function phoneExample(country) {
  const e = example(country);
  return e ? formatPhone(e.number) : "";
}

/** What has been typed so far, formatted as the person types ("(208) 555-01"). */
function formatAsYouType(input, country) {
  return new AsYouType(upper(country)).input(String(input ?? ""));
}

module.exports = { parsePhone, toE164, isValidPhone, formatPhone, callingCode, phonePlaceholder, phoneExample, formatAsYouType, EXAMPLES };
