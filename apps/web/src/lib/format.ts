// Money, numbers and dates. They follow the country (its first Markets locale,
// e.g. en-IN: ₹1,24,050.00), never the visitor's language: a language change
// never changes how a price reads, let alone what it is.

export function money(amount: number | string | null | undefined, currency: string, formatLocale: string, opts?: { whole?: boolean }): string {
  const n = Number(amount ?? 0);
  const abs = Math.abs(n);
  // whole: drop ".00" from whole amounts; never round real cents away.
  const decimals = opts?.whole && Math.round(abs * 100) % 100 === 0 ? 0 : 2;
  const body = new Intl.NumberFormat(formatLocale, {
    style: "currency",
    currency,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(abs);
  return n < 0 ? `−${body}` : body;
}

export function number(n: number, formatLocale: string, digits = 1): string {
  return new Intl.NumberFormat(formatLocale, { maximumFractionDigits: digits }).format(n);
}

export function date(iso: string | Date, formatLocale: string, timeZone?: string, opts?: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat(formatLocale, { day: "numeric", month: "short", timeZone, ...opts }).format(new Date(iso));
}

export function time(iso: string | Date, formatLocale: string, timeZone?: string): string {
  return new Intl.DateTimeFormat(formatLocale, { hour: "numeric", minute: "2-digit", timeZone }).format(new Date(iso)).toLowerCase();
}

/** "morning" | "afternoon" | "evening" by the visitor's local hour (greeting). */
export function partOfDay(d = new Date()): "morning" | "afternoon" | "evening" {
  const h = d.getHours();
  return h < 12 ? "morning" : h < 17 ? "afternoon" : "evening";
}

/** Up to two initials of a name ("Red Lantern Wok" -> "RL"), for a kitchen with no photo of its own. */
export function initials(name: string | null | undefined): string {
  return (name ?? "")
    .split(/\s+/)
    .filter((w) => /^\p{L}/u.test(w))
    .slice(0, 2)
    .map((w) => w[0]!.toLocaleUpperCase())
    .join("");
}

/** A photo URL from data: absolute URLs pass through; "/food/..." is served by the website. */
export function photo(url: string | null | undefined, width: 400 | 800 | 1600 = 800): string | null {
  if (!url) return null;
  return url.replace(/-(400|800|1600)\.webp$/, `-${width}.webp`);
}
