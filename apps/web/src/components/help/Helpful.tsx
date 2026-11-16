"use client";
// "Was this helpful?" (F9): anonymous. The browser keeps a random id so a
// second answer changes the first; core_api keeps only its hash. On "No", the
// way to contact us.
import { useEffect, useState } from "react";

import { Check } from "@/components/Icons";
import { urls } from "@/lib/client";
import { useT } from "@/lib/i18n";

const VOTER = "bg_help_voter";
const VOTED = "bg_help_voted";

function voterId(): string {
  try {
    let v = localStorage.getItem(VOTER);
    if (!v) {
      v = crypto.randomUUID().replace(/-/g, "");
      localStorage.setItem(VOTER, v);
    }
    return v;
  } catch {
    return "";
  }
}

function remembered(id: string): boolean | null {
  try {
    const all = JSON.parse(localStorage.getItem(VOTED) ?? "{}") as Record<string, boolean>;
    return id in all ? all[id]! : null;
  } catch {
    return null;
  }
}

function remember(id: string, helpful: boolean) {
  try {
    const all = JSON.parse(localStorage.getItem(VOTED) ?? "{}") as Record<string, boolean>;
    all[id] = helpful;
    localStorage.setItem(VOTED, JSON.stringify(all));
  } catch {
    /* private window: fine, we just won't remember */
  }
}

export function Helpful({ articleId }: { articleId: string }) {
  const t = useT();
  const [vote, setVote] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const v = remembered(articleId);
    if (v !== null) setVote(v); // eslint-disable-line react-hooks/set-state-in-effect -- read once from this browser after hydration
  }, [articleId]);

  async function send(helpful: boolean) {
    setBusy(true);
    setError(null);
    try {
      const r = await fetch(`${urls.core}/api/v1/help/votes`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ article_id: articleId, helpful, voter: voterId() }),
      });
      if (!r.ok) throw new Error(String(r.status));
      setVote(helpful);
      remember(articleId, helpful);
    } catch {
      setError(t("helpcentre.vote_error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="helpful-q" className="rounded-card border border-line bg-white p-5 sm:p-6" data-testid="helpful">
      {vote === null ? (
        <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
          <h2 id="helpful-q" className="text-body-lg font-bold text-kohl">{t("helpcentre.helpful_question")}</h2>
          <div className="flex gap-2">
            {[true, false].map((h) => (
              <button key={String(h)} type="button" disabled={busy} onClick={() => send(h)}
                className="h-11 min-w-[88px] rounded-pill border-[1.5px] border-line-strong bg-white px-5 text-label font-bold text-kohl hover:border-peacock hover:text-peacock disabled:opacity-50">
                {h ? t("helpcentre.yes") : t("helpcentre.no")}
              </button>
            ))}
          </div>
          {error ? <p role="alert" className="w-full text-small text-chili">{error}</p> : null}
        </div>
      ) : (
        <div role="status" className="space-y-2">
          <h2 id="helpful-q" className="flex items-center gap-2 text-body-lg font-bold text-kohl">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-peacock-tint text-peacock"><Check /></span>
            {vote ? t("helpcentre.helpful_thanks") : t("helpcentre.unhelpful_thanks")}
          </h2>
          {!vote ? (
            <p className="text-body text-muted">
              {t("helpcentre.unhelpful_body")}{" "}
              <a href="#contact" className="font-bold text-peacock underline underline-offset-2">{t("helpcentre.unhelpful_contact")}</a>
            </p>
          ) : null}
        </div>
      )}
    </section>
  );
}
