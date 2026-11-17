// /payouts/done (R10): where Stripe sends a kitchen partner or delivery partner after its
// payout set-up pages (the Account Link's return_url, ?app=kitchen|delivery), and where
// our set-up link lands when it has expired (?status=expired) or the payments partner
// didn't answer (?status=unavailable). It says what happened and opens the right app
// (its Payouts screen asks the payments partner again on return). Not for search engines.
import type { Metadata } from "next";
import Link from "next/link";

import { ErrorFrame } from "@/components/ErrorFrame";
import { libraryPhoto } from "@/lib/format";
import { getContext } from "@/lib/prefs";

type Search = Promise<Record<string, string | string[] | undefined>>;

// The apps' own links (app.json "scheme") to their Payouts screens.
const APPS = {
  kitchen: { href: "bhojango-partner://payouts", label: "payouts_done.open_kitchen" },
  delivery: { href: "bhojango-rider://payouts", label: "payouts_done.open_delivery" },
} as const;

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getContext();
  return { title: t("payouts_done.meta_title"), robots: { index: false, follow: false } };
}

export default async function PayoutsDone({ searchParams }: { searchParams: Search }) {
  const { t, country, directory } = await getContext();
  const q = await searchParams;
  const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v) ?? "";
  const status = one(q.status);
  const app = one(q.app) === "delivery" ? "delivery" : one(q.app) === "kitchen" ? "kitchen" : null;
  const [title, body] = status === "expired" ? ["payouts_done.title_expired", "payouts_done.body_expired"]
    : status === "unavailable" ? ["payouts_done.title_unavailable", "payouts_done.body_unavailable"]
      : ["payouts_done.title", "payouts_done.body"];
  const apps = app ? [APPS[app]] : [APPS.kitchen, APPS.delivery];
  const hero = libraryPhoto(country?.hero_photo ?? directory.hero_photo, 800);
  return (
    <ErrorFrame photo={hero} title={t(title)} body={t(body)}>
      <nav aria-label={t("payouts_done.ways")}>
        <ul className="m-0 flex list-none flex-col gap-3 p-0 sm:flex-row sm:flex-wrap">
          {apps.map((a, i) => (
            <li key={a.href}>
              <a href={a.href}
                className={`flex min-h-12 items-center justify-center rounded-full px-6 text-label ${i === 0
                  ? "bg-[#0B5D66] text-white hover:bg-[#08484F]" : "border border-[#E2E7E8] text-[#111418] hover:border-[#0B5D66] hover:text-[#0B5D66]"}`}>
                {t(a.label)}
              </a>
            </li>
          ))}
          <li>
            <Link href="/help" className="flex min-h-12 items-center justify-center rounded-full border border-[#E2E7E8] px-6 text-label text-[#111418] hover:border-[#0B5D66] hover:text-[#0B5D66]">
              {t("payouts_done.help")}
            </Link>
          </li>
        </ul>
      </nav>
    </ErrorFrame>
  );
}
