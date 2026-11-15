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

/**
 * A day and month in a time zone: an order's city (its `time_zone`), else the country's.
 * A calendar day from the API ("2026-11-14") is that day in every zone.
 */
export function date(iso: string | Date, formatLocale: string, timeZone?: string | null, opts?: Intl.DateTimeFormatOptions): string {
  return format(iso, formatLocale, { day: "numeric", month: "short", ...opts }, timeZone);
}

/** "7:05 pm" in a time zone: an order's city (its `time_zone`), else the country's; never the visitor's device. */
export function time(iso: string | Date, formatLocale: string, timeZone?: string | null): string {
  return format(iso, formatLocale, { hour: "numeric", minute: "2-digit" }, timeZone).toLowerCase();
}

function format(iso: string | Date, formatLocale: string, opts: Intl.DateTimeFormatOptions, timeZone?: string | null): string {
  const day = typeof iso === "string" && /^\d{4}-\d{2}-\d{2}$/.test(iso);
  const d = day ? new Date(`${iso as string}T12:00:00Z`) : new Date(iso);
  const zone = day ? "UTC" : timeZone || undefined;
  try {
    return new Intl.DateTimeFormat(formatLocale, { ...opts, timeZone: zone }).format(d);
  } catch {
    return new Intl.DateTimeFormat(formatLocale, opts).format(d); // an unknown zone name
  }
}

/** The hour (0-23) in a time zone; the device's clock only when no zone is known. */
export function hourIn(timeZone: string | null | undefined, d = new Date()): number {
  if (timeZone) {
    try {
      // data-ok: parses the hour, so Latin digits whatever the language
      return Number(new Intl.DateTimeFormat("en-US", { hour: "numeric", hourCycle: "h23", timeZone }).format(d)) % 24;
    } catch {
      // an unknown zone name: the device's clock below
    }
  }
  return d.getHours();
}

/**
 * "morning" | "afternoon" | "evening" at the delivery address (greeting): the hour in
 * its city's time zone (GET /discover's timezone), else its country's (Markets).
 */
export function partOfDay(timeZone: string | null | undefined, d = new Date()): "morning" | "afternoon" | "evening" {
  const h = hourIn(timeZone, d);
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

/** A photo from the website's food library by its slug (Markets' hero_photo), e.g. "/food/<slug>-800.webp". */
export function libraryPhoto(slug: string | null | undefined, width: 400 | 800 | 1600 = 800): string | null {
  return slug && /^[a-z0-9-]+$/.test(slug) ? `/food/${slug}-${width}.webp` : null;
}

/** A photo URL from data: absolute URLs pass through; "/food/..." is served by the website. */
export function photo(url: string | null | undefined, width: 400 | 800 | 1600 = 800): string | null {
  if (!url) return null;
  return url.replace(/-(400|800|1600)\.webp$/, `-${width}.webp`);
}
