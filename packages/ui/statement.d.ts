export interface BelowZeroLine {
  /** week: this week came to {amount} below zero · earlier: still {amount} below zero from earlier weeks, carried · carried: carried to next week */
  kind: "week" | "earlier" | "carried";
  /** Minor units, positive (how far below zero); absent for "carried". */
  amount?: number;
}
export declare function belowZeroLines(amount: number, carriedIn: number | null | undefined): BelowZeroLine[];
