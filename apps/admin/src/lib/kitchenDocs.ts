// The documents an application is checked against (Partners -> Applications): the
// kitchen's country's "Documents kitchens need" in Markets (country setting
// kitchen_documents, the same list the website's /partner page shows), in the order
// and with the names admins gave them. Pure (no React): test/kitchenDocs.test.ts.

/** What the application API saved (GET /user/restaurants/{id}/application). */
export interface ApplicationFields {
  fssai_number: string | null;
  fssai_expires_on: string | null;
  fssai_document_key: string | null;
  gstin: string | null;
  payout_account: string | null;
}

export interface DocRow {
  key: string;
  label: string;
  /** What the kitchen gave; null: nothing saved for this document. */
  value: string | null;
  /** The uploaded certificate, to open with GET /uploads/view. */
  fileKey: string | null;
}

interface SavedDoc { key?: unknown; title?: Record<string, unknown> }

/** The country's documents as admins saved them in Markets (English titles). */
export function marketDocs(settings: Record<string, unknown> | null | undefined): { key: string; label: string }[] {
  const raw = settings?.kitchen_documents;
  if (!Array.isArray(raw)) return [];
  return (raw as SavedDoc[])
    .map((d) => ({ key: String(d?.key ?? ""), label: String(d?.title?.en ?? "").trim() }))
    .filter((d) => d.key && d.label);
}

// Which saved application field answers a document, by the document's key in Markets.
// The application stores a food licence (number, expiry, certificate), a tax
// registration number and the payout account; a document with another key is
// not collected in the application.
const LICENCE = "fssai";
const TAX = "gstin";
const BANK = "bank";

function licence(a: ApplicationFields): string | null {
  if (!a.fssai_number) return null;
  return a.fssai_expires_on ? `${a.fssai_number} · until ${a.fssai_expires_on}` : a.fssai_number;
}

/** The payout account's status as the payments provider reports it (pending, active, restricted). */
function payout(a: ApplicationFields): string | null {
  return a.payout_account;
}

/**
 * One row per Markets document, then anything the kitchen gave that no document in
 * the list asks for (so nothing saved is hidden), then the payout account if no
 * document covers it.
 */
export function applicationDocs(a: ApplicationFields, settings: Record<string, unknown> | null | undefined): DocRow[] {
  const docs = marketDocs(settings);
  const keys = new Set(docs.map((d) => d.key));
  const rows: DocRow[] = docs.map((d) => {
    if (d.key === LICENCE) return { ...d, value: licence(a), fileKey: a.fssai_document_key };
    if (d.key === TAX) return { ...d, value: a.gstin, fileKey: null };
    if (d.key === BANK) return { ...d, value: payout(a), fileKey: null };
    return { ...d, value: null, fileKey: null };
  });
  if (!keys.has(LICENCE) && (a.fssai_number || a.fssai_document_key)) {
    rows.push({ key: LICENCE, label: "Food licence", value: licence(a), fileKey: a.fssai_document_key });
  }
  if (!keys.has(TAX) && a.gstin) rows.push({ key: TAX, label: "Tax registration", value: a.gstin, fileKey: null });
  if (!keys.has(BANK)) rows.push({ key: BANK, label: "Payout account", value: payout(a), fileKey: null });
  return rows;
}

/** Whether the application collects this document (so "not given" is the kitchen's gap, not ours). */
export function collected(key: string): boolean {
  return key === LICENCE || key === TAX || key === BANK;
}
