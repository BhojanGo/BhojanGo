// Counts in admin's English labels (R24): "1 issue to look at", "2 issues to look at".
// `word` picks the noun for a count; `count` adds the number (en-US grouping).

/** The singular for exactly 1 (or "1"), else the plural (default: singular + "s"). */
export function word(n: unknown, one: string, many = `${one}s`): string {
  return Number(n) === 1 ? one : many;
}

/** "1 issue", "2 issues", "1,204 orders". */
export function count(n: number, one: string, many = `${one}s`): string {
  return `${n.toLocaleString("en-US")} ${word(n, one, many)}`;
}
