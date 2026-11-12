import type { Metadata } from "next";
import Link from "next/link";

import { Prose } from "@/components/Prose";

export const metadata: Metadata = { title: "Help", description: "Ordering, the fair bill, delivery, cancellations and refunds on BhojanGo." };

export default function Help() {
  return (
    <Prose
      title="Help"
      intro={<>Answers to what people ask most. For a problem with an order you placed, open it from <Link href="/orders" className="font-bold text-peacock">Your orders</Link>.</>}
      sections={[
        { id: "ordering", title: "Ordering", body: <>
          <p>Pick a city, a kitchen and your dishes. Sign in with your phone number: we text you a 6-digit code, no password.</p>
          <p>At checkout choose where it goes (a saved address, or your current location) and whether to tip your rider.</p>
        </> },
        { id: "fair-bill", title: "The fair bill", body: <>
          <p>Before you pay you see every line of the bill and who gets it: <b>KITCHEN</b> (the food and packaging), <b>RIDER</b> (your tip, all of it), <b>GOVT</b> (tax) and <b>US</b> (delivery and service fees; we pay riders for every delivery separately).</p>
          <p>Offers say who pays for them. The price is held for a few minutes while you pay; if it runs out we work it out again before charging you.</p>
        </> },
        { id: "delivery", title: "Delivery and the PIN", body: <>
          <p>Follow your order live: the kitchen accepts and cooks, a rider picks it up, and the map shows them on the way.</p>
          <p>Your tracking page shows a 4-digit PIN. Give it to your rider at the door, or they take a photo of the bags where they leave them.</p>
        </> },
        { id: "cancel", title: "Cancelling", body: <>
          <p>You can cancel for a full refund until the kitchen starts cooking (a couple of minutes after it accepts). After that, ask us from the order.</p>
          <p>If the kitchen doesn&apos;t accept in time, or no rider can be found, we cancel and refund you in full automatically.</p>
        </> },
        { id: "refunds", title: "Refunds", body: <>
          <p>Something wrong or missing? Tell us from the order; we refund by item, including the tax on it, to the way you paid. Refunds reach UPI and cards in about 5–7 working days.</p>
        </> },
        { id: "payment", title: "Paying", body: <>
          <p>India: UPI, cards and wallets through Razorpay. United States: cards, Apple Pay and Google Pay through Stripe. A payment that doesn&apos;t go through isn&apos;t charged; try again while the price is held.</p>
        </> },
      ]}
    />
  );
}
