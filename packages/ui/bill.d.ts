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
export declare function money(amount: string | number, currency: string, opts?: { decimals?: number }): string;
export declare function billRows(lines: BillLine[], currency: string): BillRow[];
export declare function billTotal(lines: BillLine[]): number;
export declare const PAYEE: Record<string, string>;
