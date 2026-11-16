// /signin (WebSignIn, MWebSignIn): Phone and Email as equal tabs, Google below both.
// Phone: the code goes to /signin/code. Email: password, an email code, or a new account
// (EmailForm). ?way=email opens the Email tab; ?way=email&mode=create the new-account form.
import type { Metadata } from "next";
import Link from "next/link";

import { getContext } from "@/lib/prefs";
import { authProviders } from "@/lib/server";
import { EmailForm } from "./EmailForm";
import { GoogleSignIn } from "./GoogleSignIn";
import { safeNext } from "./next";
import { PhoneForm } from "./PhoneForm";
import { Shell } from "./Shell";
import { SignInTabs } from "./SignInTabs";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getContext();
  return { title: t("signin.title"), robots: { index: false, follow: false } };
}

export default async function SignInPage({ searchParams }: { searchParams: Promise<{ next?: string; way?: string; mode?: string }> }) {
  const { next, way, mode } = await searchParams;
  const [{ country, directory, place, t }, providers] = await Promise.all([getContext(), authProviders()]);
  const countries = directory.countries.map((c) => ({ code: c.code, name: c.name, phone_code: c.phone_code }));
  const initial = country?.code ?? countries[0]?.code ?? null;
  // Google only when the API has it set up; Apple isn't offered on the web yet.
  const google = providers?.google?.client_id ?? null;
  const to = safeNext(next);
  return (
    <Shell>
      <SignInTabs
        initial={way === "email" ? "email" : "phone"}
        phone={<PhoneForm countries={countries} initial={initial} next={to} />}
        email={<EmailForm country={initial} next={to} hasPlace={!!place} initialMode={mode === "create" ? "create" : "signin"} />}
        after={
          <>
            {google && <GoogleSignIn clientId={google} country={initial} next={to} hasPlace={!!place} />}
            <div className="mt-7 hidden rounded-2xl bg-[#F4F6F6] p-4 text-small leading-[1.5] md:block">
              <b>{t("signin.partner_q")}</b> <span className="text-[#3D4A4E]">{t("signin.partner_note")}</span>{" "}
              <Link href="/partner" className="font-bold">{t("signin.add_kitchen")}</Link> · <Link href="/ride" className="font-bold">{t("signin.ride")}</Link>
            </div>
          </>
        }
      />
    </Shell>
  );
}
