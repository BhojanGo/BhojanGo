// Ride with BhojanGo: what the pay looks like (in words: the figures live in
// the rider app and differ per city), and how to apply (the rider app).
import type { Metadata } from "next";
import Link from "next/link";

import { getContext } from "@/lib/prefs";
import { SITE } from "@/lib/server";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getContext();
  return { title: t("ride.meta_title"), description: t("ride.lead"), alternates: { canonical: `${SITE}/ride` } };
}

export default async function Ride() {
  const { t } = await getContext();
  const points = ["offer", "floor", "tips", "weekly"] as const;
  const steps = [1, 2, 3] as const;
  return (
    <div className="mx-auto max-w-3xl space-y-6 px-5 py-12">
      <div>
        <p className="text-caption text-[#0B5D66]">{t("ride.eyebrow")}</p>
        <h1 className="text-h1 leading-[1.05] tracking-[-1.2px]">{t("ride.title")}</h1>
        <p className="mt-3 text-body-lg text-[#4C5A5E]">{t("ride.lead")}</p>
      </div>

      <section aria-labelledby="pay" className="rounded-[20px] bg-[#F4F6F6] p-6">
        <h2 id="pay" className="text-h2">{t("ride.pay_title")}</h2>
        <ul className="mt-4 space-y-3">
          {points.map((p) => (
            <li key={p} className="flex gap-3">
              <span aria-hidden="true" className="mt-[7px] h-2 w-2 shrink-0 rounded-full bg-[#0B5D66]" />
              <span>
                <b>{t(`ride.pay_${p}_title`)}</b> <span className="text-[#4C5A5E]">{t(`ride.pay_${p}_body`)}</span>
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-small text-[#4C5A5E]">
          {t("ride.pay_more")}{" "}
          <Link href="/help" className="font-bold">{t("ride.help_link")}</Link>
        </p>
      </section>

      <section aria-labelledby="apply" className="rounded-[20px] border border-[#E2E7E8] bg-white p-6">
        <h2 id="apply" className="text-h2">{t("ride.apply_title")}</h2>
        <ol className="mt-4 space-y-3">
          {steps.map((n) => (
            <li key={n} className="flex items-start gap-3">
              <span aria-hidden="true" className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#0B5D66] text-caption text-white">{n}</span>
              <span>{t(`ride.apply_step${n}`)}</span>
            </li>
          ))}
        </ol>
        <p className="mt-4 text-small text-[#4C5A5E]">{t("ride.apply_note")}</p>
      </section>
    </div>
  );
}
