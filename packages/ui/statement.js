// R24: what a kitchen statement below zero says, shared by the Kitchen app and admin
// (the statement PDF does the same in Python: core_api finance service statements.below_zero_lines).
// No DOM, no React Native. Amounts are minor units, as on payout_statements.
//
// A statement's amount B is the week's own result W plus what earlier weeks left below zero
// (carried_in C, <= 0): B = W + C. Only when B is below zero is anything said:
//   - W < 0:  "This week came to |W| below zero."                                   (week)
//   - C < 0:  "Still |C| below zero from earlier weeks · carried to next week."      (earlier)
//     when W < 0 too; when W >= 0 the week covered part of it: "Still |B| ...".
//   - W < 0 and no carry: "Carried to next week." after the week line                (carried)
// The amounts shown always add up to |B|, the statement's total (nothing counted twice).

/**
 * @param {number} amount the statement's amount (B), minor units
 * @param {number | null | undefined} carriedIn what earlier weeks left below zero (C, <= 0), minor units
 * @returns {{ kind: "week" | "earlier" | "carried", amount?: number }[]} amounts are positive (how far below zero)
 */
function belowZeroLines(amount, carriedIn) {
  const b = Number(amount) || 0;
  if (b >= 0) return [];
  const c = Math.min(Number(carriedIn) || 0, 0);
  const w = b - c;
  if (w < 0) {
    return c < 0 ? [{ kind: "week", amount: -w }, { kind: "earlier", amount: -c }]
                 : [{ kind: "week", amount: -w }, { kind: "carried" }];
  }
  return [{ kind: "earlier", amount: -b }];
}

module.exports = { belowZeroLines };
