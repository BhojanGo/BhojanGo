# India readiness

What must be true before BhojanGo takes a real order in India. Boise launches first
([boise-readiness.md](boise-readiness.md)); nothing here blocks Boise. Started in round 25 (2026-11-21). Nothing
in this list is built yet unless it says so.

The facts here are for planning. Srini's CA confirms every tax and legal point before anything is built or
switched on in India.

## 1. GST tax invoice fields (CGST Rule 46): not built yet

The commission tax invoice ([R16](../STATUS.md#india-tax-rules-round-16): 18% GST on BhojanGo's commission, to the
kitchen, one per weekly statement; `backend/core_api/modules/finance/service/commission_invoice.py`) has the
invoice number, date, period, the supplier's legal name (from Markets; refused if missing, R25), the kitchen's name
and address, the commission, the GST rate and amount, and the total. Rule 46 also needs:

| Field | Today | To build |
|---|---|---|
| Supplier address and GSTIN | Printed when set in admin → Markets → India → Legal entity; the GSTIN prints as "pending registration" until then | Refuse to issue the invoice until both are set, as R25 does for the name |
| Recipient (kitchen) address and GSTIN | Address printed; GSTIN printed when the kitchen has one (`restaurants.gstin`) | Decide with the CA how to invoice a kitchen with no GSTIN (unregistered: B2C invoice, no GSTIN line) |
| SAC code | Not printed | The SAC for the commission (the CA confirms which code), a setting of the "commission tax" rule, printed on each line |
| Place of supply | Not printed | The kitchen's state (state name and its 2-digit GST state code) |
| CGST + SGST vs IGST | One "GST on commission @ 18%" line | Same state as the supplier's GSTIN: CGST 9% + SGST 9% as two lines; another state: IGST 18%. Per-order rounding stays (R17), and the invariant test checks the split adds up to the statement's GST |
| Signature or digital signature | "This is a computer-generated invoice and needs no signature." | Ask the CA: a digital signature on the PDF, or the e-invoice IRN and QR code (if BhojanGo's turnover needs e-invoicing) |

Also on the list:
- **Invoice number:** Rule 46 allows at most 16 characters, consecutive within a financial year. Today's numbers
  (`CI-YYYYMM-<8 characters of the statement id>`, like `CI-202611-3F2A9C1E`) are 18 characters and not
  consecutive. A per-financial-year sequence is needed.
- **Credit notes** when a statement's commission changes after its invoice (a refund in a later week).

## 2. Questions for the CA (rounds 15 and 16)

Each of these is a business rule per country, editable in admin and marked "Confirm with CA" until confirmed:

1. **GST on food under section 9(5).** Does BhojanGo, as the e-commerce operator, pay the 5% GST on restaurant
   services for every kitchen (registered or not)? How should the customer's receipt show it, and does Reconciliation
   book it as tax owed by the platform?
2. **Discounts and the tax base.** A kitchen-funded discount lowers the taxable value. Does a platform-funded one?
   (Today it doesn't: the Hyderabad worked example is ₹640.72 with GST on food ₹28.50.)
3. **GST on commission:** 18% on BhojanGo's commission, taken from the kitchen's payout, with the invoice in section 1.
   The SAC code, and whether the delivery fee is a separate supply with its own rate.
4. **TDS under section 194-O** on kitchen payouts: the rate (India is 0% in the rules until confirmed), and how
   kitchens get their TDS certificates.
5. **TCS under section 52** on anything not covered by section 9(5) (for example packaged goods).
6. **Rounding:** GST on commission per order, rounded to the paisa, then added up (R17). Is that acceptable?
7. **Payments to delivery partners:** any TDS on them, and what the weekly statement must show.

## 3. Company and platform details (legal entity in Markets)

Required before launch in India; admin flags each one as "required before launch" until it is set:

- **CIN** of DeepTrics Software Solutions Pvt Ltd (format checked in admin).
- **GSTIN** of the company, in the state it registers in (format checked).
- **Registered address,** support email and phone.
- **Grievance officer** (name, email, phone), shown on the Terms and Privacy pages and the website footer
  (Consumer Protection (E-Commerce) Rules 2020; IT Rules 2021). Confirm the response times with the lawyer.

## 4. Per kitchen

- **FSSAI licence or registration:** the kitchen enters the number and expiry and uploads the document (built, P19);
  a kitchen whose licence has expired is hidden from customers. Still to do: someone checks each number against
  FSSAI's register before the kitchen goes live, and the licence number is shown on the kitchen's page as FSSAI
  requires of e-commerce food businesses.
- **GSTIN** when the kitchen has one (built: `restaurants.gstin`, used on the invoice).
- **Bank account and KYC** for payouts (Razorpay Route or Stripe Connect in India: decided in the payments setup).

## 5. Owner and status

| Item | Owner | Status |
|---|---|---|
| GST invoice fields (section 1) | Claude Code builds once the CA confirms section 2 | Not started |
| CA questions (section 2) | Srini with the CA | Not started |
| CIN, GSTIN, address, grievance officer (section 3) | Srini enters them in admin | Not started (name set: DeepTrics Software Solutions Pvt Ltd) |
| FSSAI checks per kitchen (section 4) | Srini's onboarding team | Not started |
