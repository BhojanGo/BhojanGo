// /signin (WebSignIn, MWebSignIn): phone sign-in; the code goes to /signin/code.
import type { Metadata } from "next";

import { getContext } from "@/lib/prefs";
import { authProviders } from "@/lib/server";
import { GoogleSignIn } from "./GoogleSignIn";
import { safeNext } from "./next";
import { Shell } from "./Shell";
import { PhoneForm } from "./PhoneForm";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getContext();
  return { title: t("signin.title"), robots: { index: false, follow: false } };
}

export default async function SignInPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const { next } = await searchParams;
  const [{ country, directory, place }, providers] = await Promise.all([getContext(), authProviders()]);
  const countries = directory.countries.map((c) => ({ code: c.code, name: c.name, phone_code: c.phone_code }));
  const initial = country?.code ?? countries[0]?.code ?? null;
  // Google only when the API has it set up; Apple isn't offered on the web yet.
  const google = providers?.google?.client_id ?? null;
  return (
    <Shell>
      <PhoneForm countries={countries} initial={initial} next={safeNext(next)}>
        {google && <GoogleSignIn clientId={google} country={initial} next={safeNext(next)} hasPlace={!!place} />}
      </PhoneForm>
    </Shell>
  );
}

