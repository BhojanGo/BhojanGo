// Phone numbers for people to read (R22): the E.164 the API stores ("+12085550291") in its
// country's usual grouping ("+1 208-555-0291"). Only for the visible text: tel: links and
// everything sent to the API keep the E.164.
//
// A small table for the countries we run in, not libphonenumber-js: its "min" metadata is
// ~80 KB (minified) in every web, admin and app bundle to format two countries, and its
// grouping for +1 ("+1 208 555 0291") is not the one we want ("+1 208-555-0291").
//
// Rules (national digits after the country code):
//   +1   US, Canada (NANP)  10 digits      +1 208-555-0291
//   +91  India              10 digits      +91 98765 43210
//   +44  United Kingdom     10 digits      +44 7700 900123 (mobiles 7…), +44 20 7946 0958 (2…)
//   +61  Australia           9 digits      +61 412 345 678 (mobiles 4…), +61 2 9876 5432
//   +64  New Zealand       8-10 digits     +64 21 123 4567 (mobiles 2…), +64 9 123 4567
//   +65  Singapore           8 digits      +65 8123 4567
//   +971 United Arab Emirates 9 digits     +971 50 123 4567 (mobiles 5…), +971 4 123 4567
// Anything else (no "+", letters, an unknown country code, a length the country does not use)
// comes back exactly as given: never throws, never drops a digit.

/** Split `digits` into groups of the given sizes (the last size takes what is left). */
function groups(digits, sizes) {
  const out = [];
  let i = 0;
  for (let n = 0; n < sizes.length && i < digits.length; n++) {
    const last = n === sizes.length - 1;
    out.push(last ? digits.slice(i) : digits.slice(i, i + sizes[n]));
    i += sizes[n];
  }
  return out;
}

/** Country code -> (national digits) -> the formatted national part, or null if it doesn't fit. */
const COUNTRIES = {
  1: (d) => (d.length === 10 ? groups(d, [3, 3, 4]).join("-") : null),
  91: (d) => (d.length === 10 ? groups(d, [5, 5]).join(" ") : null),
  44: (d) => {
    if (d.length !== 10) return null;
    return (d[0] === "2" ? groups(d, [2, 4, 4]) : groups(d, [4, 6])).join(" ");
  },
  61: (d) => {
    if (d.length !== 9) return null;
    return (d[0] === "4" || d[0] === "5" ? groups(d, [3, 3, 3]) : groups(d, [1, 4, 4])).join(" ");
  },
  64: (d) => {
    if (d[0] === "2") return d.length >= 8 && d.length <= 10 ? groups(d, [2, 3, 9]).join(" ") : null;
    return d.length === 8 ? groups(d, [1, 3, 4]).join(" ") : null;
  },
  65: (d) => (d.length === 8 ? groups(d, [4, 4]).join(" ") : null),
  971: (d) => {
    if (d.length === 9 && d[0] === "5") return groups(d, [2, 3, 4]).join(" ");
    if (d.length === 8) return groups(d, [1, 3, 4]).join(" ");
    return null;
  },
};

/**
 * A phone number for people to read: "+12085550291" -> "+1 208-555-0291",
 * "+919876543210" -> "+91 98765 43210". Already formatted numbers come back in the same
 * format; null/undefined/"" give ""; anything it cannot place comes back unchanged.
 */
function formatPhone(value) {
  if (value == null || value === "") return "";
  let raw = "";
  try {
    raw = String(value);
    const s = raw.trim();
    // Only "+" then digits with the usual separators; anything else is not ours to touch.
    if (!/^\+[\d\s().-]+$/.test(s)) return raw;
    const digits = s.slice(1).replace(/[\s().-]/g, "");
    if (!/^[1-9]\d{6,14}$/.test(digits)) return raw;
    for (const len of [1, 2, 3]) {
      const code = digits.slice(0, len);
      const fmt = COUNTRIES[code];
      if (!fmt) continue;
      const national = fmt(digits.slice(len));
      return national ? `+${code} ${national}` : raw;
    }
    return raw;
  } catch {
    return raw;
  }
}

module.exports = { formatPhone };
