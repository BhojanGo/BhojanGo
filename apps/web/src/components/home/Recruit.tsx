"use client";
// "For kitchens" / "For riders" (WebLanding): only for signed-out visitors on
// the first-visit page. Signed in, there is no marketing (footer links only).
import Link from "next/link";

import { useHydrated, useSession } from "@/lib/client";
import { useT } from "@/lib/i18n";

export function RecruitCards() {
  const t = useT();
  const hydrated = useHydrated();
  const user = useSession((s) => s.user);
  if (hydrated && user) return null;
  return (
    <section aria-label={t("home.work_with_us")} className="mx-auto grid max-w-[1440px] gap-4 px-5 pt-14 md:grid-cols-2 md:gap-6 md:px-16 md:pt-20">
      <div className="rounded-[28px] bg-[#EFF6F6] p-7 md:p-10">
        <div className="text-caption text-[#0B5D66]">{t("home.kitchens_eyebrow")}</div>
        <h2 className="mt-[10px] text-h1 tracking-[-0.8px]">{t("home.kitchens_title")}</h2>
        <p className="mt-3 max-w-[440px] text-body leading-[1.5] text-muted">{t("home.kitchens_body")}</p>
        <Link href="/partner" className="mt-5 inline-flex h-[52px] items-center rounded-full bg-[#0B5D66] px-6 font-bold text-white hover:bg-[#083F46] hover:text-white">
          {t("home.kitchens_cta")}
        </Link>
      </div>
      <div className="rounded-[28px] bg-[#0C1416] p-7 text-[#F2F5F5] md:p-10">
        <div className="text-caption text-[#E8A93C]">{t("home.riders_eyebrow")}</div>
        <h2 className="mt-[10px] text-h1 tracking-[-0.8px]">{t("home.riders_title")}</h2>
        <p className="mt-3 max-w-[440px] text-body leading-[1.5] text-[#A9B8BA]">{t("home.riders_body")}</p>
        <Link href="/ride" className="mt-5 inline-flex h-[52px] items-center rounded-full bg-[#E8A93C] px-6 font-bold text-[#111418] hover:text-[#111418]">
          {t("home.riders_cta")}
        </Link>
      </div>
    </section>
  );
}
