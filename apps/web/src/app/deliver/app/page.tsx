// /deliver/app: where the QR code on /deliver points. The store links are the
// country's Markets settings (delivery_partner.app_links); until BhojanGo Delivery
// is published they are empty and the page says so plainly (no made-up links).
import type { Metadata } from "next";
import Link from "next/link";

import { flatCities } from "@/components/discover/places";
import { getContext } from "@/lib/prefs";
import { deliveryTerms, SITE } from "@/lib/server";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getContext();
  return { title: t("deliver_page.app_title"), description: t("deliver_page.app_lead"), alternates: { canonical: `${SITE}/deliver/app` } };
}

export default async function DeliveryApp({ searchParams }: { searchParams: Promise<{ country?: string }> }) {
  const ctx = await getContext();
  const { t } = ctx;
  const asked = ((await searchParams).country ?? "").toUpperCase();
  const code = ctx.directory.countries.some((k) => k.code === asked) ? asked : ctx.country?.code;
  const city = flatCities(ctx.directory).find((c) => c.country === code && c.status === "live");
  const terms = city ? await deliveryTerms(city.code) : null;
  const apps = terms && terms !== "error" ? terms.apps : null;
  const stores = [
    apps?.android ? { href: apps.android, label: t("deliver_page.done_android") } : null,
    apps?.ios ? { href: apps.ios, label: t("deliver_page.done_ios") } : null,
  ].filter((x): x is { href: string; label: string } => !!x);

  return (
    <div className="mx-auto w-full max-w-[1200px] px-4 py-12 md:px-8 md:py-16 lg:px-12">
      <div className="max-w-[640px]">
        <p className="m-0 text-caption text-peacock">{t("deliver_page.eyebrow")}</p>
        <h1 className="m-0 mt-3 text-h1 tracking-[-0.8px]">{t("deliver_page.app_title")}</h1>
        <p className="m-0 mt-3 text-body-lg text-muted">{t("deliver_page.app_lead")}</p>
        {terms === "error" ? (
          <div role="alert" className="mt-8 rounded-[20px] border border-line p-6">
            <p className="m-0 text-body">{t("common.error")}</p>
            <Link href="/deliver/app" className="mt-3 inline-block text-label">{t("deliver_page.try_again")}</Link>
          </div>
        ) : stores.length ? (
          <div className="mt-8 flex flex-col gap-3 sm:flex-row" data-testid="app-stores">
            {stores.map((s) => (
              <a key={s.href} href={s.href} rel="noopener noreferrer" className="inline-flex h-14 items-center justify-center rounded-full bg-kohl px-7 text-label text-white hover:text-white">
                {s.label}
              </a>
            ))}
          </div>
        ) : (
          <div className="mt-8 rounded-[20px] bg-porcelain p-6" data-testid="app-not-yet">
            <h2 className="m-0 text-h3">{t("deliver_page.app_not_yet_title")}</h2>
            <p className="m-0 mt-2 text-body text-muted">{t("deliver_page.app_not_yet_body")}</p>
          </div>
        )}
        <div className="mt-8 flex flex-col gap-3 text-body sm:flex-row sm:items-center sm:gap-6">
          <span>
            {t("deliver_page.app_signup")}{" "}
            <Link href="/deliver#get-started" className="font-bold">{t("deliver_page.get_started")}</Link>
          </span>
          <Link href="/help" className="font-bold">{t("deliver_page.app_help")}</Link>
        </div>
      </div>
    </div>
  );
}
