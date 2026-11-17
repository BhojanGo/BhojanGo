// Sign up to deliver (app/join.tsx): the date of birth as the API checks it.

export type DatePart = "day" | "month" | "year";

/**
 * Whole years from a date of birth to the country's today (both "YYYY-MM-DD"),
 * as POST /riders/apply counts them (markets.service.delivery.age_on); null for a
 * date that can't be a birthday (malformed, not a real day, in the future, over 100).
 */
export function ageOn(born: string, today: string): number | null {
  const b = /^(\d{4})-(\d{2})-(\d{2})$/.exec(born);
  const t = /^(\d{4})-(\d{2})-(\d{2})$/.exec(today);
  if (!b || !t || born > today) return null;
  const [by, bm, bd] = [Number(b[1]), Number(b[2]), Number(b[3])];
  const [ty, tm, td] = [Number(t[1]), Number(t[2]), Number(t[3])];
  const real = new Date(Date.UTC(by, bm - 1, bd));
  if (real.getUTCFullYear() !== by || real.getUTCMonth() !== bm - 1 || real.getUTCDate() !== bd) return null; // 31 June
  const age = ty - by - (tm < bm || (tm === bm && td < bd) ? 1 : 0);
  return age > 100 ? null : age;
}

/** Day, month and year in the order the country writes dates (en-US: month first); day-month-year if unknown. */
export function dateOrder(locale: string | undefined): DatePart[] {
  try {
    const parts = new Intl.DateTimeFormat(locale, { year: "numeric", month: "2-digit", day: "2-digit" })
      .formatToParts(new Date(Date.UTC(2000, 10, 22)))
      .map((p) => p.type)
      .filter((p): p is DatePart => p === "day" || p === "month" || p === "year");
    return parts.length === 3 ? parts : ["day", "month", "year"];
  } catch {
    return ["day", "month", "year"];
  }
}
