// Times on a city's clock (R27): an order's times show in its city's time zone (the API's
// `time_zone`, Markets data) with the zone named ("11:34 am MST"), never the viewer's browser zone.
// Pure (no React): test/zone.test.ts.

/** "MST" / "MDT" / "IST" for a zone at an instant; a zone with no common abbreviation: its city ("(Boise)"). */
export function zoneLabel(zone: string, at: Date = new Date()): string {
  for (const locale of ["en-US", "en-IN"]) {
    try {
      const name = new Intl.DateTimeFormat(locale, { timeZone: zone, timeZoneName: "short" })
        .formatToParts(at).find((p) => p.type === "timeZoneName")?.value;
      if (name && !/^(GMT|UTC)[+-]/.test(name)) return name;
    } catch {
      return "";
    }
  }
  return `(${(zone.split("/").pop() ?? zone).replace(/_/g, " ")})`;
}

/** "11:34 am MST": a time on the zone's clock with the zone named. No zone: the browser's clock, unlabelled. */
export function clockIn(iso: string | null | undefined, zone?: string | null): string {
  if (!iso) return "–";
  const d = new Date(iso);
  const opts: Intl.DateTimeFormatOptions = { hour: "numeric", minute: "2-digit" };
  if (zone) {
    try {
      const t = d.toLocaleTimeString("en-US", { ...opts, timeZone: zone }).toLowerCase();
      const label = zoneLabel(zone, d);
      return label ? `${t} ${label}` : t;
    } catch {
      // an unknown zone name: the browser's clock below
    }
  }
  return d.toLocaleTimeString("en-US", opts).toLowerCase();
}

/** "21 Nov, 11:34 am MST": a day and time on the zone's clock. */
export function dateTimeIn(iso: string | null | undefined, zone?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  let day: string;
  try {
    day = d.toLocaleDateString("en-GB", { day: "numeric", month: "short", ...(zone ? { timeZone: zone } : {}) });
  } catch {
    day = d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  }
  return `${day}, ${clockIn(iso, zone)}`;
}

interface ZoneTree { code: string; timezone: string; regions: { timezone: string | null; cities: { code: string; timezone: string | null }[] }[] }

/** A city code's zone from the Markets tree admin already loads: the city's own, else its state's, else its country's. */
export function cityZone(markets: readonly ZoneTree[] | undefined, city: string | null | undefined): string | null {
  if (!markets || !city) return null;
  for (const k of markets) {
    for (const r of k.regions) {
      const c = r.cities.find((x) => x.code === city);
      if (c) return c.timezone || r.timezone || k.timezone;
    }
  }
  return null;
}
