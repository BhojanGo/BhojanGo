// /signin/forgot: ask for a link to choose a new password (works once, for 30 minutes).
import type { Metadata } from "next";

import { getContext } from "@/lib/prefs";
import { Shell } from "../Shell";
import { ForgotForm } from "./ForgotForm";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getContext();
  return { title: t("auth.forgot_title"), robots: { index: false, follow: false } };
}

export default async function ForgotPage({ searchParams }: { searchParams: Promise<{ email?: string }> }) {
  const { email } = await searchParams;
  return (
    <Shell>
      <ForgotForm initialEmail={(email ?? "").slice(0, 254)} />
    </Shell>
  );
}
