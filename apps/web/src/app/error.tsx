"use client";
// Something broke while showing a page (R8): the site's frame stays (header,
// footer), the page says so in the visitor's language and how to recover, never
// the error itself. "Try again" re-renders the page (a passing API blip); the
// error goes to the browser console for whoever is debugging.
import { useEffect } from "react";

import { ErrorFrame, WayList } from "@/components/ErrorFrame";
import { useT } from "@/lib/i18n";

export default function PageError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const t = useT();
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <ErrorFrame photo={null} title={t("errors.title_error")} body={t("errors.body_error")}>
      <div>
        <button
          type="button"
          onClick={reset}
          className="inline-flex min-h-12 items-center rounded-full bg-[#0B5D66] px-6 text-label font-bold text-white hover:bg-[#083F46]"
        >
          {t("errors.try_again")}
        </button>
      </div>
      <WayList
        label={t("errors.popular")}
        ways={[
          { href: "/", label: t("errors.go_home") },
          { href: "/cities", label: t("errors.where_we_deliver") },
          { href: "/help", label: t("errors.help") },
        ]}
      />
    </ErrorFrame>
  );
}
