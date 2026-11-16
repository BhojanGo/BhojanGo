import type { Metadata } from "next";

import { Prose } from "@/components/Prose";

export const metadata: Metadata = { title: "Terms", description: "The terms for ordering on BhojanGo." };

export default function Terms() {
  return (
    <Prose
      title="Terms of use"
      updated="November 2026"
      intro="These terms apply whenever you order on BhojanGo."
      sections={[
        { id: "service", title: "1. What BhojanGo does", body: <p>BhojanGo connects you with independent kitchens and delivery partners. The kitchen prepares your food and is responsible for it; the delivery partner delivers it; we run the ordering, payment and support.</p> },
        { id: "account", title: "2. Your account", body: <p>You sign in with a phone number you control. Keep access to it: anyone who receives your code can use your account. You must be 18 or older to order.</p> },
        { id: "prices", title: "3. Prices and the bill", body: <>
          <p>Menu prices are set by the kitchens. Before you pay we show the whole bill in local currency (INR or USD): food, delivery, service, any small-order or late-night fee, tax and tip, each with who receives it. You pay exactly the total shown.</p>
          <p>Offers state who funds them. We don&apos;t pre-select tips or add fees after you pay.</p>
        </> },
        { id: "cancel", title: "4. Cancelling and refunds", body: <>
          <p>You can cancel for a full refund until the kitchen starts preparing your order. Orders the kitchen doesn&apos;t accept in time, or that no delivery partner can deliver, are cancelled and refunded in full.</p>
          <p>If an item is wrong, missing or not up to standard, we refund that item and its tax. Refunds go back to the original payment method.</p>
        </> },
        { id: "delivery", title: "5. Delivery", body: <p>Arrival times are estimates. The delivery partner confirms delivery with the PIN on your tracking page or a photo at your door.</p> },
        { id: "food", title: "6. Food and allergies", body: <p>Kitchens describe their dishes. If you have an allergy, contact the kitchen through support before ordering; we can&apos;t guarantee a kitchen is free of any ingredient.</p> },
        { id: "liability", title: "7. Liability", body: <p>Our liability for an order is limited to what you paid for it, except where the law doesn&apos;t allow that limit.</p> },
        { id: "law", title: "8. Governing law", body: <p>An order is governed by the law of the country, and where it has its own, the state or province, where you receive it, including its consumer protection law.</p> },
        { id: "contact", title: "9. Contact", body: <p>Questions about these terms: legal@bhojango.com.</p> },
      ]}
    />
  );
}
