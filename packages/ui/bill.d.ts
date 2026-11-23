export interface BillLine {
  code: string;
  label: string;
  amount: string | number;
  funded_by?: string | null;
  detail?: Record<string, unknown> | null;
}
export interface BillRow {
  label: string;
  payee: string;
  amount: string;
  accent?: boolean;
  struck?: string | null;
}
export declare function money(amount: string | number, currency: string): string;
export declare function shownLines<L extends { amount: string | number }>(lines: L[]): L[];
export declare function billRows(lines: BillLine[], currency: string): BillRow[];
export declare function billTotal(lines: BillLine[]): number;
export declare const PAYEE: Record<string, string>;
/** R29: who gets this line of this bill (on a bill with a platform fee, the delivery fee is the delivery partner's). */
export declare function payeeOf(line: { code: string }, lines: readonly { code: string }[]): string;
export interface BillRefund { amount: string | number; kind?: string; reason?: string | null; items?: string[] }
export interface ReceiptRefund { amount: number; reason: string; items: string[] }
export declare const REFUND_REASONS: string[];
export declare function receiptRefunds(bill: { total: string | number; paid?: string | number | null; refunds?: BillRefund[] | null },
  cancelled: boolean): { refunds: ReceiptRefund[]; refunded: number; paid: number };
