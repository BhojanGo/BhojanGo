# The finance model, and how every finance number follows it (round 40)

## The model (source of truth)

| Who | Gets |
|---|---|
| Customer pays | food + packaging + delivery fee + platform fee + tax + tip |
| Restaurant | food + packaging − commission (0% by default) − offers it funds − **the card/payment fee for the whole charge** − refunds for its own mistakes |
| Delivery partner | delivery fee + tip (100% of both) |
| Government | tax (sales tax / GST; in India also GST on commission and TDS, both taken from the restaurant) |
| BhojanGo | platform fee (+ any commission) − offers it funds − the refunds it bears. **BhojanGo pays no card fees.** |

    captured − refunded = restaurants + card fees + delivery partners + tax + BhojanGo

Checked to the cent and the paisa by `backend/core_api/integration/test_r40_reconciliation.py` (US: delivery with a
tip, a BhojanGo-funded offer with an open chargeback, pickup, a cancelled and refunded order; India: Spice Route's 15%
commission deal, GST on it, a refund for the restaurant's mistake and one for the delivery's). Each order's shares are
worked out from its own bill lines; Reconciliation, the payout run, the restaurant statements and the contribution
report must show the same totals.

## Audit: every finance number

| Screen · number | Formula (source) | Was | Now |
|---|---|---|---|
| Contribution · Commission | Σ snapshot `split.detail.commission` (`finance/service/contribution.py`) | Matched. The US $0.44/order is not in the seed: the admin e2e's commission test sets a 12% Boise override and delivers an order with it (left in that environment's data). A fresh seed has no US order with commission; the only non-zero rule is Spice Route's 15% (India, dev/QA). | Unchanged (0% in the US) |
| Contribution · Customer fees | delivery + platform + service + small-order + busy-hour + late-night fee lines | Matched | Unchanged |
| Contribution · Offers we fund | Σ `split.detail.platform_funded_offers` | Matched | Unchanged |
| Contribution · Delivery partner pay | Σ delivery fee (+ busy-hour) to the partner; tips excluded | Matched | Unchanged |
| Contribution · **Payment fees** | provider fee (actual, else the `payment_fees` rule) **minus** the card fee | **Mismatch**: BhojanGo was charged what was left (the Stripe Tax 0.5% and rounding: ~$0.21/order on QA) | **Removed.** Card fees are shown under the total as "Card fees (paid by restaurants, not BhojanGo)", for information |
| Contribution · Refunds we pay | refunded − what the restaurant is charged for its own mistakes | Matched | Unchanged |
| Contribution · Platform keeps | platform − payment fees − refunds − top-ups | Mismatch (took payment fees) | **"BhojanGo keeps"** = platform − refunds BhojanGo bears − top-ups |
| Reconciliation · Captured / Refunded | Σ succeeded payment intents / refunds of the week's delivered orders | Matched | Unchanged |
| Reconciliation · Restaurants are owed | Σ restaurant statement nets (after the card fee) | Matched | Unchanged |
| Reconciliation · Delivery partners are owed | Σ partner statements (delivery fee + tip) | Matched | Unchanged |
| Reconciliation · Tax owed | customers' tax + GST on commission + TDS | Matched | Unchanged |
| Reconciliation · Platform revenue | captured − refunded − restaurants − partners − tax | **Mismatch**: included the card fees (money that goes to the card processor) | **"BhojanGo keeps"** = captured − refunded − restaurants − **card fees** − partners − tax |
| Reconciliation · **Payment fees** ($13.64) | all provider fees on the week's orders | **Mismatch**: counted the card fees the restaurants already paid, as BhojanGo's | **Removed**; new line "Card fees (paid by restaurants)" = Σ the card fee on the restaurant statements |
| Reconciliation · Platform after payment fees | platform revenue − payment fees | Mismatch (double count) | **Removed** |
| Reconciliation · Restaurants are owed vs paid ($242.07 vs $136.05), partners owed vs payout ($38.00 vs $24.00) | "owed" is worked out now from every order delivered in the week; the payout run is what was prepared earlier (plus R23 carried balances) | Not explained on screen | **"Not in this payout yet: $X (N orders: restaurants $…, delivery partners $…). Delivered after this payout run was prepared: they are paid with the next run."** Held chargeback money is listed there too. Carried balances keep their own lines. |
| Statement · card fee (per order) | 2.9% + $0.30 of the charge **less the tip** | Mismatch (the model: the whole charge) | 2.9% + $0.30 of the **whole charge**, tip included (`pricing/service/fees.py`) |
| Payout run · restaurants / partners | the statements when the run was prepared | Matched | Unchanged; the difference to "owed" is now labelled |
| Partner statement | delivery fee + tip | Matched | Unchanged |
| Chargeback hold | every open dispute held the restaurant's share | Mismatch (fraud is BhojanGo's) | Held only for food quality (`product_unacceptable`) or not received (`product_not_received`); fraud and every other reason: nothing held, BhojanGo bears it |

## Worked example: one Boise order through every screen

Boise Bowl Co.; dishes at 3.99 + 10.99 + 22.00; 3 miles away (billed 3.91 mi locally: the straight line × 1.3 road
factor; the same 2–4 mi band); $3 tip; card. Run with `tools/finance/worked_example.py` on the local stack.

| | Amount | Where it shows |
|---|---|---|
| Food | $36.98 | the bill |
| Delivery fee (2–4 mi band) | $4.50 | the bill |
| Platform fee (10% of food) | $3.70 | the bill |
| Idaho sales tax (6% of food + platform fee) | $2.44 | the bill |
| Tip | $3.00 | the bill |
| **Customer pays** | **$50.62** | the bill; Reconciliation "Captured" 50.62 |
| Card fee (2.9% × 50.62 + $0.30) | $1.77 | restaurant statement line "Card fee −1.77"; Reconciliation "Card fees (paid by restaurants)" 1.77; Contribution card fees 1.77 |
| **Restaurant receives** (36.98 − 1.77) | **$35.21** | restaurant statement line net 35.21; payout run; Reconciliation "Restaurants are owed" 35.21 |
| **Delivery partner receives** (4.50 + 3.00) | **$7.50** | partner statement line 7.50; Reconciliation 7.50 |
| **Tax** | **$2.44** | Reconciliation "Tax owed" 2.44 |
| **BhojanGo keeps** | **$3.70** | Reconciliation "BhojanGo keeps" 3.70; Contribution "BhojanGo keeps" 3.70 |
| Check | 35.21 + 1.77 + 7.50 + 2.44 + 3.70 = 50.62 | |

Before round 40 the same order gave the restaurant $35.30 (card fee $1.68, on the charge less the tip),
Reconciliation's "Platform revenue" $5.38 and, after "Payment fees" $1.77, "Platform after payment fees" $3.61;
Contribution took $0.09 of "Payment fees" from BhojanGo (with Stripe Tax in production, $0.34).
