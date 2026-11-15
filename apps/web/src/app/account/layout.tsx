// The account pages (orders, favourites, profile) share the account frame:
// signed-in only, the account navigation on the left (a row on phones).
import type { Metadata } from "next";

import { AccountShell } from "@/components/account/AccountShell";

// Personal pages: never in search results.
export const metadata: Metadata = { robots: { index: false, follow: false } };

export default function AccountLayout({ children }: { children: React.ReactNode }) {
  return <AccountShell>{children}</AccountShell>;
}
