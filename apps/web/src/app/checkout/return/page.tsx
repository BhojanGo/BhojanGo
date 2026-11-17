// /checkout/return: where Stripe sends the customer back after a bank page
// (3-D Secure, or a wallet that redirects). Waits for the webhook-driven
// payment status, then opens the order or offers to try again.
import type { Metadata } from "next";
import { Suspense } from "react";

import { getContext } from "@/lib/prefs";
import { PaymentReturn } from "./PaymentReturn";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getContext();
  return { title: t("checkout.return_title"), robots: { index: false, follow: false } };
}

export default function PaymentReturnPage() {
  return (
    <Suspense>
      <PaymentReturn />
    </Suspense>
  );
}
