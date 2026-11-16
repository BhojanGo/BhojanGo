"use client";
// "Still need help?" at the bottom of every Help page (F9).
// Signed in: pick a recent order → report a problem with it (the report flow,
// /account/orders/<id>/report) or write to support about it; or write about
// something else. Signed out: a contact form (name, email, topic, message) that
// becomes a support ticket answered by email. Both are rate-limited in core_api;
// the form has a field people never see, which bots fill in.
import Link from "next/link";
import { useEffect, useId, useState } from "react";

import { isActive, orderCode, type Order } from "@/components/account/shared";
import { Check } from "@/components/Icons";
import { authed, urls, useHydrated, useSession } from "@/lib/client";
import { TOPICS, type HelpTopic } from "@/lib/help";
import { useFormat, useLanguage, useT } from "@/lib/i18n";

const field = "mt-1.5 block w-full rounded-card border-[1.5px] border-line-strong bg-white px-3.5 text-body font-normal text-kohl outline-none focus:border-peacock focus:ring-2 focus:ring-peacock/25";

function readCookie(name: string): string | null {
  const m = document.cookie.split("; ").find((c) => c.startsWith(`${name}=`));
  return m ? decodeURIComponent(m.slice(name.length + 1)) : null;
}

export function HelpContact({ topic }: { topic?: HelpTopic }) {
  const t = useT();
  const hydrated = useHydrated();
  const user = useSession((s) => s.user);
  return (
    <section id="contact" aria-labelledby="contact-title" className="scroll-mt-24 rounded-card bg-white p-5 sm:p-8">
      <div className="max-w-2xl space-y-2">
        <h2 id="contact-title" className="text-h2 text-kohl">{t("helpcentre.contact_title")}</h2>
        <p className="text-body text-muted">
          {!hydrated ? " " : user ? t("helpcentre.contact_body_signed_in") : t("helpcentre.contact_body_signed_out")}
        </p>
      </div>
      <div className="mt-6">
        {!hydrated ? (
          <div aria-hidden="true" className="space-y-3">
            <div className="h-12 animate-pulse rounded-card bg-porcelain" />
            <div className="h-12 animate-pulse rounded-card bg-porcelain" />
          </div>
        ) : user ? (
          <SignedIn topic={topic} customer={user.role === "customer"} />
        ) : (
          <ContactForm topic={topic} />
        )}
      </div>
    </section>
  );
}

function TopicSelect({ value, onChange, id }: { value: string; onChange: (v: HelpTopic) => void; id: string }) {
  const t = useT();
  return (
    <select id={id} value={value} onChange={(e) => onChange(e.target.value as HelpTopic)} className={`${field} h-12`}>
      {TOPICS.map((k) => <option key={k} value={k}>{t(`helpcentre.topics.${k}.title`)}</option>)}
    </select>
  );
}

function Sent({ title, body, onAgain }: { title: string; body: string; onAgain: () => void }) {
  const t = useT();
  return (
    <div role="status" className="flex gap-4 rounded-card bg-peacock-mist p-5" data-testid="contact-sent">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-peacock text-white"><Check size={18} /></span>
      <div className="space-y-1.5">
        <p className="text-body-lg font-bold text-kohl">{title}</p>
        <p className="text-body text-muted">{body}</p>
        <button type="button" onClick={onAgain} className="min-h-[44px] text-label font-bold text-peacock">{t("helpcentre.send_another")}</button>
      </div>
    </div>
  );
}

function errorText(t: ReturnType<typeof useT>, e: unknown): string {
  const m = (e as Error)?.message ?? "";
  return /429|Rate limit|Too Many/i.test(m) ? t("helpcentre.too_many") : t("helpcentre.send_error");
}

function ContactForm({ topic }: { topic?: HelpTopic }) {
  const t = useT();
  const { language, country } = useLanguage();
  const id = useId();
  const [f, setF] = useState({ name: "", email: "", topic: topic ?? "orders", message: "", website: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState<{ name: string; email: string } | null>(null);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF((x) => ({ ...x, [k]: e.target.value }));

  if (sent) {
    return <Sent title={t("helpcentre.sent_title")} body={t("helpcentre.sent_body_email", sent)}
      onAgain={() => { setSent(null); setF((x) => ({ ...x, message: "" })); }} />;
  }
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await fetch(`${urls.core}/api/v1/help/contact`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ ...f, name: f.name.trim(), email: f.email.trim(), message: f.message.trim(), language,
          country: country?.code ?? null, city: readCookie("bg_city") }),
      });
      if (r.status === 429) throw new Error("429");
      if (r.status === 422) {
        setError(t("helpcentre.form_invalid"));
        return;
      }
      if (!r.ok) throw new Error(String(r.status));
      setSent({ name: f.name.trim(), email: f.email.trim() });
    } catch (err) {
      setError(errorText(t, err));
    } finally {
      setBusy(false);
    }
  }
  const ok = f.name.trim().length >= 2 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(f.email.trim()) && f.message.trim().length >= 10;
  return (
    <form onSubmit={submit} className="grid max-w-2xl gap-4 sm:grid-cols-2" data-testid="contact-form" noValidate>
      <label className="text-label font-semibold text-kohl">
        {t("helpcentre.form_name")}
        <input value={f.name} onChange={set("name")} required minLength={2} maxLength={80} autoComplete="name" className={`${field} h-12`} />
      </label>
      <label className="text-label font-semibold text-kohl">
        {t("helpcentre.form_email")}
        <input type="email" value={f.email} onChange={set("email")} required maxLength={200} autoComplete="email" inputMode="email" className={`${field} h-12`} />
      </label>
      <label htmlFor={`${id}-topic`} className="text-label font-semibold text-kohl sm:col-span-2">
        {t("helpcentre.form_topic")}
        <TopicSelect id={`${id}-topic`} value={f.topic} onChange={(v) => setF((x) => ({ ...x, topic: v }))} />
      </label>
      <label className="text-label font-semibold text-kohl sm:col-span-2">
        {t("helpcentre.form_message")}
        <textarea value={f.message} onChange={set("message")} required minLength={10} maxLength={2000} rows={5}
          aria-describedby={`${id}-hint`} className={`${field} py-3`} />
        <span id={`${id}-hint`} className="mt-1.5 block text-small font-normal text-muted">{t("helpcentre.form_message_hint")}</span>
      </label>
      {/* For bots only: people never see it (core_api drops messages that fill it in). */}
      <div aria-hidden="true" className="absolute -left-[9999px] h-px w-px overflow-hidden">
        <label>Website<input tabIndex={-1} autoComplete="off" value={f.website} onChange={set("website")} /></label>
      </div>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-3 sm:col-span-2">
        <button type="submit" disabled={busy || !ok}
          className="h-12 rounded-pill bg-peacock px-6 text-label font-bold text-white hover:bg-peacock-deep disabled:opacity-40">
          {busy ? t("helpcentre.form_sending") : t("helpcentre.form_send")}
        </button>
        <Link href="/signin?next=/help%23contact" className="min-h-[44px] content-center text-label font-bold text-peacock">{t("helpcentre.sign_in_orders")}</Link>
      </div>
      {error ? <p role="alert" className="text-small text-chili sm:col-span-2">{error}</p> : null}
    </form>
  );
}

function SignedIn({ topic, customer }: { topic?: HelpTopic; customer: boolean }) {
  const t = useT();
  const f = useFormat();
  const [orders, setOrders] = useState<Order[] | null>(customer ? null : []);
  const [failed, setFailed] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);
  const [writing, setWriting] = useState(false);
  useEffect(() => {
    if (!customer) return;
    let live = true;
    authed<{ items: Order[] }>("GET", "/api/v1/orders?page=1&limit=5")
      .then((r) => live && setOrders(r.items.filter((o) => o.status !== "pending_payment")))
      .catch(() => {
        if (live) {
          setOrders([]);
          setFailed(true);
        }
      });
    return () => {
      live = false;
    };
  }, [customer]);
  const order = orders?.find((o) => o.id === picked) ?? null;

  if (writing) {
    return <MessageForm topic={topic} order={order} onBack={() => setWriting(false)} />;
  }
  return (
    <div className="space-y-5">
      {customer ? (
        <fieldset className="space-y-3">
          <legend className="text-label font-bold text-kohl">{t("helpcentre.recent_orders")}</legend>
          {orders === null ? (
            <div aria-hidden="true" className="grid gap-2 sm:grid-cols-2">{[0, 1].map((i) => <div key={i} className="h-[72px] animate-pulse rounded-card bg-porcelain" />)}</div>
          ) : orders.length === 0 ? (
            <p className="text-body text-muted">{failed ? t("helpcentre.orders_error") : t("helpcentre.no_orders")}</p>
          ) : (
            <div className="grid gap-2 sm:grid-cols-2" data-testid="help-orders">
              {orders.map((o) => {
                const at = o.placed_at ?? o.created_at;
                const z = f.zone(o.time_zone);
                const on = picked === o.id;
                return (
                  <label key={o.id}
                    className={`flex min-h-[72px] cursor-pointer items-center gap-3 rounded-card border-[1.5px] p-3.5 ${on ? "border-peacock bg-peacock-mist" : "border-line hover:bg-porcelain"}`}>
                    <input type="radio" name="help-order" value={o.id} checked={on} onChange={() => setPicked(o.id)} className="h-5 w-5 accent-peacock" />
                    <span className="min-w-0">
                      <span className="block truncate text-label font-bold text-kohl">{o.restaurant_name}</span>
                      <span className="block text-small text-muted tabular-nums">
                        {orderCode(o.id)} · {z.date(at)} · {f.money(o.total, o.currency)} · {t(`account.status.${o.status}`)}
                      </span>
                    </span>
                  </label>
                );
              })}
            </div>
          )}
        </fieldset>
      ) : null}
      <div className="flex flex-wrap gap-3">
        {order && order.status === "delivered" ? (
          <Link href={`/account/orders/${order.id}/report`} className="inline-flex h-12 items-center rounded-pill bg-peacock px-6 text-label font-bold text-white hover:bg-peacock-deep">
            {t("helpcentre.report_problem")}
          </Link>
        ) : order && isActive(order.status) ? (
          <Link href={`/orders/${order.id}/track`} className="inline-flex h-12 items-center rounded-pill bg-peacock px-6 text-label font-bold text-white hover:bg-peacock-deep">
            {t("helpcentre.track_order")}
          </Link>
        ) : null}
        <button type="button" onClick={() => setWriting(true)}
          className={`inline-flex h-12 items-center rounded-pill px-6 text-label font-bold ${order && (order.status === "delivered" || isActive(order.status)) ? "border-[1.5px] border-line-strong text-kohl hover:border-peacock" : "bg-peacock text-white hover:bg-peacock-deep"}`}>
          {order ? t("helpcentre.message_about_order") : t("helpcentre.message_support")}
        </button>
      </div>
    </div>
  );
}

function MessageForm({ topic, order, onBack }: { topic?: HelpTopic; order: Order | null; onBack: () => void }) {
  const t = useT();
  const { language } = useLanguage();
  const id = useId();
  const [kind, setKind] = useState<HelpTopic>(topic ?? "orders");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  if (sent) {
    return <Sent title={t("helpcentre.sent_title")} body={t("helpcentre.sent_body_signed_in")} onAgain={() => { setSent(false); setMessage(""); onBack(); }} />;
  }
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await authed("POST", "/api/v1/help/messages", { topic: kind, message: message.trim(), order_id: order?.id ?? null, language });
      setSent(true);
    } catch (err) {
      setError(errorText(t, err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="grid max-w-2xl gap-4" data-testid="message-form">
      {order ? <p className="text-body text-kohl">{t("helpcentre.about_order", { order: `${orderCode(order.id)} · ${order.restaurant_name}` })}</p> : null}
      <label htmlFor={`${id}-topic`} className="text-label font-semibold text-kohl">
        {t("helpcentre.form_topic")}
        <TopicSelect id={`${id}-topic`} value={kind} onChange={setKind} />
      </label>
      <label className="text-label font-semibold text-kohl">
        {t("helpcentre.form_message")}
        <textarea value={message} onChange={(e) => setMessage(e.target.value)} required minLength={10} maxLength={2000} rows={5} className={`${field} py-3`} />
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={busy || message.trim().length < 10}
          className="h-12 rounded-pill bg-peacock px-6 text-label font-bold text-white hover:bg-peacock-deep disabled:opacity-40">
          {busy ? t("helpcentre.form_sending") : t("helpcentre.form_send")}
        </button>
        <button type="button" onClick={onBack} className="h-12 rounded-pill px-4 text-label font-bold text-peacock hover:bg-peacock-mist">{t("common.back")}</button>
      </div>
      {error ? <p role="alert" className="text-small text-chili">{error}</p> : null}
    </form>
  );
}
