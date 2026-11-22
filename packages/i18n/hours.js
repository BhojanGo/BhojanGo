// When a kitchen opens, in words (R27): "6:30 am" later today, "Sat 6:30 am" on another day.
// The time is on the kitchen's city clock (its IANA zone), in the country's format (formatLocale:
// en-US and en-IN both say "6:30 am"); the weekday is in the visitor's language ("శని" in Telugu).
// Plain JS for the website and the apps; Intl only, nothing hand-rolled.

function parts(date, locale, options) {
  try {
    return new Intl.DateTimeFormat(locale, options).format(date);
  } catch {
    const { timeZone: _ignored, ...rest } = options; // an engine without that zone: the device's
    return new Intl.DateTimeFormat(locale, rest).format(date);
  }
}

function dayKey(date, timeZone) {
  // data-ok: a comparison key, never shown
  return parts(date, "en-CA", { year: "numeric", month: "2-digit", day: "2-digit", ...(timeZone ? { timeZone } : {}) });
}

/**
 * { time: "6:30 am", day: null } when `iso` is later on `now`'s day in `timeZone`, else
 * { time, day: "Sat" } (the weekday in `language`). Null for a missing or bad time.
 */
function opensWhen(iso, { timeZone, formatLocale, language, now } = {}) {
  if (!iso) return null;
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return null;
  const zone = timeZone ? { timeZone } : {};
  const time = parts(at, formatLocale || undefined, { hour: "numeric", minute: "2-digit", ...zone }).toLowerCase();
  const same = dayKey(at, timeZone) === dayKey(now || new Date(), timeZone);
  return { time, day: same ? null : parts(at, language || formatLocale || undefined, { weekday: "short", ...zone }) };
}

/**
 * The status worded with the catalogs: keys.today ("Closed · opens {time}") for later today, else
 * keys.day ("Closed · opens {day} {time}"). Defaults: common.closed_opens / common.closed_opens_day.
 * Null when there's no time.
 */
function opensLabel(t, iso, options, keys) {
  const w = opensWhen(iso, options);
  if (!w) return null;
  const k = keys || { today: "common.closed_opens", day: "common.closed_opens_day" };
  return w.day ? t(k.day, { day: w.day, time: w.time }) : t(k.today, { time: w.time });
}

/** "08:00" (a wall-clock time from the API, e.g. the city's delivery hours) -> "8:00 am" in the country's format. */
function wallClock(hhmm, formatLocale) {
  const m = /^(\d{1,2}):(\d{2})/.exec(hhmm || "");
  if (!m) return null;
  const d = new Date(Date.UTC(2000, 0, 1, Number(m[1]), Number(m[2])));
  return parts(d, formatLocale || undefined, { hour: "numeric", minute: "2-digit", timeZone: "UTC" }).toLowerCase();
}

module.exports = { opensWhen, opensLabel, wallClock };
