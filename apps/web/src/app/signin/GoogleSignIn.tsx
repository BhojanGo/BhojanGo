"use client";
// "Continue with Google" (WebSignIn), only when the API says Google sign-in is
// set up (/auth/providers). Google's own button (Google Identity Services,
// accounts.google.com); its ID token goes to POST /auth/social-login, which
// returns the same tokens as the phone flow, adopted the same way.
import Script from "next/script";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { urls, useSession } from "@/lib/client";
import { useLanguage, useT } from "@/lib/i18n";
import { placeFromDefaultAddress } from "./afterSignIn";

interface Gis {
  accounts: {
    id: {
      initialize: (o: { client_id: string; callback: (r: { credential?: string }) => void; ux_mode?: "popup"; itp_support?: boolean; use_fedcm_for_button?: boolean }) => void;
      renderButton: (el: HTMLElement, o: Record<string, string | number>) => void;
    };
  };
}

export function GoogleSignIn({ clientId, country, next, hasPlace }: { clientId: string; country: string | null; next: string; hasPlace: boolean }) {
  const t = useT();
  const { language } = useLanguage();
  const router = useRouter();
  const adopt = useSession((s) => s.adopt);
  const box = useRef<HTMLDivElement>(null);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const gis = (window as unknown as { google?: Gis }).google;
    if (!loaded || !gis || !box.current) return;
    gis.accounts.id.initialize({
      client_id: clientId,
      ux_mode: "popup",
      use_fedcm_for_button: true,
      callback: async ({ credential }) => {
        if (!credential) return;
        setBusy(true);
        setError(null);
        try {
          const r = await fetch(`${urls.core}/api/v1/auth/social-login`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ provider: "google", token: credential, ...(country ? { country } : {}) }),
          });
          if (!r.ok) throw new Error(String(r.status));
          await adopt((await r.json()) as { access_token: string; refresh_token: string });
          await placeFromDefaultAddress(hasPlace);
          router.replace(next);
          router.refresh();
        } catch {
          setError(t("signin.google_failed"));
          setBusy(false);
        }
      },
    });
    gis.accounts.id.renderButton(box.current, {
      type: "standard",
      theme: "outline",
      size: "large",
      shape: "pill",
      text: "continue_with",
      logo_alignment: "center",
      width: Math.min(400, box.current.clientWidth || 400),
      locale: language,
    });
  }, [loaded, clientId, country, next, hasPlace, adopt, router, t, language]);

  return (
    <div>
      <Script src="https://accounts.google.com/gsi/client" strategy="afterInteractive" onReady={() => setLoaded(true)} />
      <div className="my-6 flex items-center gap-3 text-sm text-[#4C5A5E]">
        <span className="h-px flex-grow bg-[#E2E7E8]" />
        {t("signin.or")}
        <span className="h-px flex-grow bg-[#E2E7E8]" />
      </div>
      <div ref={box} className="flex min-h-[44px] w-full justify-center" aria-busy={busy} />
      {busy && <p role="status" className="m-0 mt-2 text-center text-sm text-[#4C5A5E]">{t("signin.signing_in")}</p>}
      {error && <p role="alert" className="m-0 mt-2 text-sm font-semibold text-[#8C1D18]">{error}</p>}
    </div>
  );
}
