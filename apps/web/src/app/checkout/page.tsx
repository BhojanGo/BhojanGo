// /checkout (WebCheckout, MWebCheckout): signed in only; the address in the
// header (cookie) is offered first, then the saved addresses.
import type { Metadata } from "next";

import { getContext } from "@/lib/prefs";
import { Checkout } from "./Checkout";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getContext();
  return { title: t("checkout.title"), robots: { index: false, follow: false } };
}

export default async function CheckoutPage() {
  const { place, directory } = await getContext();
  // Each country's ways to pay come from Markets (country settings), not from code.
  const methods = Object.fromEntries(directory.countries.map((c) => [c.code, c.payment_methods]));
  return <Checkout place={place} countryMethods={methods} />;
}
