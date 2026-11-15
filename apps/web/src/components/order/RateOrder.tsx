"use client";
// "Rate this order" after delivery (tracking page, order receipt): 1-5 stars
// and an optional comment -> POST /orders/{id}/rating. Once saved, the rating
// is shown instead. The order's own `rated`/`rating` fields say whether it is
// rated; without them (an older API) GET /orders/{id}/rating is asked.
import { useEffect, useId, useState } from "react";

import { authed } from "@/lib/client";
import { orderRating, type OrderRating } from "@/lib/contract";
import { useT } from "@/lib/i18n";
import { Star } from "../Icons";

function Stars({ value, size = 22 }: { value: number; size?: number }) {
  return (
    <span className="inline-flex gap-[2px]" aria-hidden="true">
      {[1, 2, 3, 4, 5].map((n) => (
        <Star key={n} size={size} color={n <= value ? "#E8A93C" : "#C9D3D4"} fill={n <= value ? "#E8A93C" : "none"} />
      ))}
    </span>
  );
}

export function RateOrder({ orderId, order, compact }: { orderId: string; order: unknown; compact?: boolean }) {
  const t = useT();
  const known = orderRating(order);
  const [fetched, setFetched] = useState<{ id: string; rating: OrderRating | null } | null>(null);
  const [saved, setSaved] = useState<OrderRating | null>(null);
  const [stars, setStars] = useState(0);
  const [hover, setHover] = useState(0);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const commentId = useId();
  const titleId = useId();

  // Older API: the order doesn't say, so ask for its rating (none yet -> 404).
  const ask = known.rated === null && !known.rating;
  useEffect(() => {
    if (!ask) return;
    let live = true;
    authed<OrderRating | null>("GET", `/api/v1/orders/${orderId}/rating`)
      .then((r) => live && setFetched({ id: orderId, rating: r && r.stars ? r : null }))
      .catch(() => live && setFetched({ id: orderId, rating: null }));
    return () => {
      live = false;
    };
  }, [ask, orderId]);

  const rating = saved ?? known.rating ?? (fetched?.id === orderId ? fetched.rating : null);
  if (ask && !fetched && !saved) return null;

  const box = compact ? "mt-6 rounded-2xl bg-[#F4F6F6] p-4" : "rounded-[24px] border border-[#E2E7E8] p-[22px]";
  if (rating) {
    return (
      <section className={box} aria-labelledby={titleId}>
        <h2 id={titleId} className="m-0 text-label">{t("rating.your_rating")}</h2>
        <div className="mt-2 flex items-center gap-2">
          <Stars value={rating.stars} />
          <span className="sr-only">{t("rating.stars", { count: rating.stars })}</span>
        </div>
        {rating.comment && <p className="m-0 mt-2 text-body text-[#4C5A5E]">“{rating.comment}”</p>}
        <p className="m-0 mt-2 text-small text-[#4C5A5E]">{t("rating.thanks")}</p>
      </section>
    );
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!stars) return;
    setBusy(true);
    setError(null);
    const body: OrderRating = { stars, ...(comment.trim() ? { comment: comment.trim() } : {}) };
    try {
      const r = await authed<OrderRating | undefined>("POST", `/api/v1/orders/${orderId}/rating`, body);
      setSaved(r && r.stars ? r : body);
    } catch {
      setError(t("rating.failed"));
    } finally {
      setBusy(false);
    }
  }

  const shown = hover || stars;
  return (
    <section className={box} aria-labelledby={titleId}>
      <h2 id={titleId} className={compact ? "m-0 text-label" : "m-0 text-h3"}>{t("rating.title")}</h2>
      <p className="m-0 mt-1 text-small text-[#4C5A5E]">{t("rating.sub")}</p>
      <form onSubmit={submit} className="mt-3">
        <div role="radiogroup" aria-label={t("rating.stars_label")} className="flex gap-1" onMouseLeave={() => setHover(0)}>
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              type="button"
              role="radio"
              aria-checked={stars === n}
              aria-label={t("rating.stars", { count: n })}
              onClick={() => setStars(n)}
              onMouseEnter={() => setHover(n)}
              className="flex h-11 w-11 items-center justify-center rounded-full hover:bg-[#F6E7CC]"
            >
              <Star size={28} color={n <= shown ? "#E8A93C" : "#C9D3D4"} fill={n <= shown ? "#E8A93C" : "none"} />
            </button>
          ))}
        </div>
        {stars > 0 && (
          <>
            <label htmlFor={commentId} className="mt-3 block text-label">{t("rating.comment")}</label>
            <textarea
              id={commentId}
              value={comment}
              maxLength={500}
              rows={3}
              onChange={(e) => setComment(e.target.value)}
              placeholder={t("rating.comment_placeholder")}
              className="mt-1 w-full rounded-[14px] border-[1.5px] border-[#C9D3D4] bg-white p-3 text-body outline-none focus:border-[#0B5D66]"
            />
            <button type="submit" disabled={busy} className="mt-3 h-11 rounded-full bg-[#0B5D66] px-5 font-bold text-white hover:bg-[#083F46] disabled:opacity-60">
              {busy ? t("rating.saving") : t("rating.submit")}
            </button>
          </>
        )}
        {error && <p role="alert" className="m-0 mt-2 text-label text-[#8C1D18]">{error}</p>}
      </form>
    </section>
  );
}
