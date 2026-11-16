// /signin/reset?token=...: choose a new password with the emailed link.
import type { Metadata } from "next";

import { getContext } from "@/lib/prefs";
import { Shell } from "../Shell";
import { ResetForm } from "./ResetForm";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getContext();
  // The token is in the address: never indexed, never sent on as a referrer.
  return { title: t("auth.reset_title"), robots: { index: false, follow: false }, referrer: "no-referrer" };
}

export default async function ResetPage({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  const { token } = await searchParams;
  return (
    <Shell>
      <ResetForm token={(token ?? "").slice(0, 200)} />
    </Shell>
  );
}
