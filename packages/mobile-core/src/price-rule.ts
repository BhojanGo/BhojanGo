// R44: the menu price rule the API applies (catalog price_problem), as a pure function so the tablet can check a price as
// it is typed. More than 0 (an option may be 0); at most 2 decimals; whole units where the currency has no cents in use.
export type PriceRuleProblem = "required" | "whole" | "cents";

export function priceRule(text: string, whole: boolean, allowZero = false): PriceRuleProblem | null {
  const v = text.trim().replace(",", ".");
  if (!/^\d+(\.\d+)?$/.test(v) || (!allowZero && Number(v) <= 0)) return "required";
  if (whole && Number(v) !== Math.trunc(Number(v))) return "whole";
  if (!whole && (v.split(".")[1] ?? "").replace(/0+$/, "").length > 2) return "cents";
  return null;
}
