// The footer (design: WebLanding/WebHome). It never lists cities: it links to
// /cities. Recruitment (kitchens, riders) lives here as links only.
import Link from "next/link";

import { getContext } from "@/lib/prefs";
import { LogoMark } from "./Icons";

export async function SiteFooter() {
  const { t, country } = await getContext();
  const operator = country?.legal?.name;  // R15: per detected country, from Markets
  const col = "flex min-w-0 flex-col gap-[10px] [overflow-wrap:anywhere]"; // R27: long Tamil words wrap in the 2-column phone footer
  return (
    <footer className="mt-[72px] bg-[#F4F6F6] print:hidden">
      <div className="grid container-page grid-cols-2 gap-8 py-12 text-body md:grid-cols-[1.4fr_1fr_1fr_1fr]">
        <div className="col-span-2 md:col-span-1">
          <div className="flex items-center gap-[10px]">
            <LogoMark size={30} />
            <b className="text-h3">{t("common.brand")}</b>
          </div>
          <div className="mt-3 leading-normal text-muted">{t("common.tagline")}</div>
        </div>
        <div className={col}>
          <b>{t("footer.where_we_deliver")}</b>
          <Link href="/cities">{t("footer.all_cities")}</Link>
          <Link href="/cities#suggest">{t("footer.suggest_city")}</Link>
        </div>
        <div className={col}>
          <b>{t("footer.work_with_us")}</b>
          <Link href="/partner">{t("footer.add_kitchen")}</Link>
          <Link href="/deliver">{t("footer.ride")}</Link>
        </div>
        <div className={col}>
          <b>{t("footer.help")}</b>
          <Link href="/help">{t("footer.help_centre")}</Link>
          <Link href="/account/orders">{t("footer.your_orders")}</Link>
          <Link href="/terms">{t("footer.terms")}</Link>
          <Link href="/privacy">{t("footer.privacy")}</Link>
          <Link href="/credits">{t("footer.photo_credits")}</Link>
        </div>
      </div>
      {operator ? (
        <p data-testid="footer-operator" className="container-page border-t border-[#E2E7E8] py-4 text-small text-muted">
          {t("common.operated_by", { name: operator })}
        </p>
      ) : null}
    </footer>
  );
}
