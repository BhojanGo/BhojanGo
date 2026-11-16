"use client";
// The last resort (R8): the site's own frame failed (usually the API is down, so
// the layout could not load the visitor's country and language). It replaces the
// whole document, so it brings its own <html>, fonts and words: the language the
// visitor picked (bg_lang cookie) or their browser's, and only that language's
// messages, loaded when this page is shown. Never the error itself.
import { createTranslator, pickLanguage, type Messages, type Translate } from "@bhojango/i18n";
import Link from "next/link";
import { useEffect, useState } from "react";

import { ErrorFrame, WayList } from "@/components/ErrorFrame";
import { LogoMark } from "@/components/Icons";
import { fontVariables } from "./fonts";
import "./globals.css";

const LOAD: Record<string, () => Promise<{ default: Messages }>> = {
  en: () => import("@bhojango/i18n/messages/en.json"),
  hi: () => import("@bhojango/i18n/messages/hi.json"),
  te: () => import("@bhojango/i18n/messages/te.json"),
  ta: () => import("@bhojango/i18n/messages/ta.json"),
  kn: () => import("@bhojango/i18n/messages/kn.json"),
  mr: () => import("@bhojango/i18n/messages/mr.json"),
  bn: () => import("@bhojango/i18n/messages/bn.json"),
  es: () => import("@bhojango/i18n/messages/es.json"),
};

function visitorLanguage(): string {
  const chosen = /(?:^|;\s*)bg_lang=([^;]+)/.exec(document.cookie)?.[1];
  return pickLanguage({ chosen: chosen ? decodeURIComponent(chosen) : null, acceptLanguage: navigator.languages?.join(",") ?? navigator.language });
}

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const [words, setWords] = useState<{ lang: string; t: Translate } | null>(null);
  useEffect(() => {
    console.error(error);
  }, [error]);
  useEffect(() => {
    const lang = visitorLanguage();
    const want = LOAD[lang] ?? LOAD.en!;
    void Promise.all([want(), LOAD.en!()])
      .then(([m, en]) => setWords({ lang, t: createTranslator(lang, m.default, en.default) }))
      .catch(() => LOAD.en!().then((en) => setWords({ lang: "en", t: createTranslator("en", en.default, en.default) })).catch(() => undefined));
  }, []);
  const t = words?.t;
  return (
    <html lang={words?.lang ?? "en"}>
      <body className={`${fontVariables} bg-white font-sans text-[#111418] antialiased`}>
        <header className="border-b border-[#E2E7E8]">
          <div className="container-page flex h-16 items-center md:h-[76px]">
            <Link href="/" aria-label={t ? t("common.home") : "BhojanGo"} className="flex items-center gap-[10px] text-[#111418]">
              <LogoMark />
              <span className="text-h2 tracking-[-0.4px]">BhojanGo</span>
            </Link>
          </div>
        </header>
        <main id="main" aria-busy={!t}>
          {t && (
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
          )}
        </main>
      </body>
    </html>
  );
}
