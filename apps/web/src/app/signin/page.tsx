// /signin (WebSignIn, MWebSignIn): phone sign-in; the code goes to /signin/code.
import type { Metadata } from "next";

import { getContext } from "@/lib/prefs";
import { safeNext } from "./next";
import { Shell } from "./Shell";
import { PhoneForm } from "./PhoneForm";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getContext();
  return { title: t("signin.title"), robots: { index: false, follow: false } };
}

export default async function SignInPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const { next } = await searchParams;
  const { country, directory } = await getContext();
  const countries = directory.countries.map((c) => ({ code: c.code, name: c.name, phone_code: c.phone_code }));
  return (
    <Shell>
      <PhoneForm countries={countries} initial={country?.code ?? countries[0]?.code ?? null} next={safeNext(next)} />
    </Shell>
  );
}

