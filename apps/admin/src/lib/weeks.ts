// R41: payout week labels for admin Finance (pure, tested in test/weeks.test.ts).

/** "Mon 9 Nov – Sun 15 Nov 2026" for a run's period (end is the next Monday, not included). R41: always with the year
 * (a run from another year read as this year's: "Mon 15 Dec" was 15 Dec 2008, a Monday); both years when they differ. */
export function weekLabel(start: string, end: string): string {
  const at = (iso: string, back = 0) => {
    const d = new Date(`${iso}T12:00:00Z`);
    d.setUTCDate(d.getUTCDate() - back);
    return d;
  };
  const fmt = (d: Date, year: boolean) => d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short",
    ...(year ? { year: "numeric" } : {}), timeZone: "UTC" }).replace(",", "");
  const a = at(start), b = at(end, 1);
  return `${fmt(a, a.getUTCFullYear() !== b.getUTCFullYear())} – ${fmt(b, true)}`;
}
