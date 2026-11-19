// Account deletion and legal links (R19), the pure part (node --test runs it):
// the website's legal page for a country, and why the server didn't delete an
// account, in the person's words. src/account.tsx draws them.

type T = (key: string, vars?: Record<string, string | number>) => string;

/** The website's Terms or Privacy policy page for a country (apps/web: /terms and /privacy, ?country=XX). */
export function legalPageUrl(web: string, kind: "terms" | "privacy", country?: string | null): string {
  return `${web.replace(/\/+$/, "")}/${kind}${country ? `?country=${encodeURIComponent(country)}` : ""}`;
}

/**
 * Why deleting didn't happen: the server waits while it still owes the person money
 * (409 MONEY_OWED, with the amount, formatted) or while their orders are on the way
 * (409 ORDERS_IN_PROGRESS). Anything else: "try again". `e` is an ApiError
 * (status, code, body) or anything thrown.
 */
export function deleteAccountProblem(e: unknown, t: T): string {
  const err = e as { status?: number; code?: string; body?: { detail?: { code?: string; amount?: string } } } | null;
  if (err && err.status === 409) {
    const detail = err.body?.detail;
    const code = err.code ?? detail?.code;
    if (code === "MONEY_OWED") return t("account.delete.money_owed", { amount: detail?.amount ?? "" });
    if (code === "ORDERS_IN_PROGRESS") return t("account.delete.orders_in_progress");
  }
  return t("account.privacy.failed");
}
