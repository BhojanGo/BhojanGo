// /signin/code (WebOTP): the 6-digit code sent to the phone.
import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { getContext } from "@/lib/prefs";
import { safeNext } from "../next";
import { Shell } from "../Shell";
import { CodeForm } from "./CodeForm";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getContext();
  return { title: t("signin.code_title"), robots: { index: false, follow: false } };
}

export default async function CodePage({ searchParams }: { searchParams: Promise<{ phone?: string; country?: string; next?: string }> }) {
  const { phone, country, next } = await searchParams;
  const { place } = await getContext();
  if (!phone || !country) redirect(`/signin?next=${encodeURIComponent(safeNext(next))}`);
  return (
    <Shell>
      <CodeForm phone={phone} country={country} next={safeNext(next)} hasPlace={!!place} />
    </Shell>
  );
}
