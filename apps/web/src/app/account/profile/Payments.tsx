"use client";
// Saved payment methods (WebProfile): brand, last four, expiry; make default,
// remove. A card number never touches BhojanGo: real cards are added in the
// payment provider's own form at checkout. With the test provider (local and
// QA) you can save a test card here: a random pm_fake_ token plus the brand,
// the last 4 digits and the expiry you type.

import { useEffect, useState } from "react";

import { authed } from "@/lib/client";
import { useT } from "@/lib/i18n";
import { card, ghost, h2, input, link, primary, Row } from "./ui";

interface Method {
  id: string;
  provider: string;
  brand: string;
  last4: string;
  exp_month: number;
  exp_year: number;
  is_default: boolean;
}

// Local and QA run the fake payment provider; a live site sets its real one.
const TEST_PROVIDER = (process.env.NEXT_PUBLIC_PAYMENTS_PROVIDER ?? "fake") === "fake";
const BRANDS = ["visa", "mastercard", "amex", "rupay", "discover"];
const brandName = (b: string) => (b === "amex" ? "Amex" : b.charAt(0).toUpperCase() + b.slice(1));

function fakeToken(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(12));
  return `pm_fake_${Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("")}`;
}

function AddCard({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const t = useT();
  const now = new Date();
  const [brand, setBrand] = useState(BRANDS[0]);
  const [last4, setLast4] = useState("");
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear() + 2);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    const expired = year < now.getFullYear() || (year === now.getFullYear() && month < now.getMonth() + 1);
    if (!/^\d{4}$/.test(last4) || expired) return setProblem(t("account.payments.invalid"));
    setBusy(true);
    setProblem(null);
    try {
      // Only the token and display details: never a card number.
      await authed("POST", "/api/v1/me/payment-methods", { provider: "fake", provider_token: fakeToken(), brand, last4, exp_month: month, exp_year: year });
      onDone();
    } catch {
      setProblem(t("account.profile.save_failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={save} aria-labelledby="add-card" className="mt-4 rounded-2xl border border-[#E2E7E8] bg-[#FAFBFB] p-4 md:p-5">
      <h3 id="add-card" className="font-bold">{t("account.payments.add_title")}</h3>
      <p className="mt-1 text-small text-muted">{t("account.payments.add_note")}</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-4">
        <label className="text-label text-muted">
          {t("account.payments.brand")}
          <select value={brand} onChange={(e) => setBrand(e.target.value)} className={input}>
            {BRANDS.map((b) => <option key={b} value={b}>{brandName(b)}</option>)}
          </select>
        </label>
        <label className="text-label text-muted">
          {t("account.payments.last4")}
          <input
            value={last4}
            onChange={(e) => setLast4(e.target.value.replace(/\D/g, "").slice(0, 4))}
            inputMode="numeric"
            pattern="\d{4}"
            maxLength={4}
            required
            autoComplete="off"
            className={input}
          />
        </label>
        <label className="text-label text-muted">
          {t("account.payments.exp_month")}
          <select value={month} onChange={(e) => setMonth(Number(e.target.value))} className={input}>
            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => <option key={m} value={m}>{String(m).padStart(2, "0")}</option>)}
          </select>
        </label>
        <label className="text-label text-muted">
          {t("account.payments.exp_year")}
          <select value={year} onChange={(e) => setYear(Number(e.target.value))} className={input}>
            {Array.from({ length: 16 }, (_, i) => now.getFullYear() + i).map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </label>
      </div>
      {problem && <p role="alert" className="mt-3 text-label text-[#8C1D18]">{problem}</p>}
      <div className="mt-4 flex flex-wrap gap-[10px]">
        <button type="submit" disabled={busy} className={primary}>{t("account.payments.save")}</button>
        <button type="button" onClick={onCancel} className={ghost}>{t("common.cancel")}</button>
      </div>
    </form>
  );
}

export function Payments() {
  const t = useT();
  const [list, setList] = useState<Method[] | null | "error">(null);
  const [reload, setReload] = useState(0);
  const [adding, setAdding] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    authed<Method[]>("GET", "/api/v1/me/payment-methods")
      .then((r) => live && setList(r))
      .catch(() => live && setList("error"));
    return () => {
      live = false;
    };
  }, [reload]);
  const refresh = () => setReload((n) => n + 1);

  async function act(m: Method, what: "default" | "remove") {
    if (what === "remove" && !window.confirm(t("account.payments.confirm_remove", { brand: brandName(m.brand), last4: m.last4 }))) return;
    setProblem(null);
    try {
      if (what === "default") await authed("POST", `/api/v1/me/payment-methods/${m.id}/default`);
      else await authed("DELETE", `/api/v1/me/payment-methods/${m.id}`);
      refresh();
    } catch {
      setProblem(t("account.profile.save_failed"));
    }
  }

  return (
    <section id="payments" aria-labelledby="payments-title" className={card}>
      <h2 id="payments-title" className={h2}>{t("account.payments.title")}</h2>
      <p className="mt-[2px] text-small text-muted">{t("account.payments.note")}</p>
      {list === null && <p role="status" className="mt-3 text-muted">{t("account.loading")}</p>}
      {list === "error" && <p className="mt-3 text-muted">{t("account.payments.unavailable")}</p>}
      {Array.isArray(list) && (
        <div className="mt-3">
          {!list.length && <p className="py-3 text-muted">{t("account.payments.empty")}</p>}
          {list.map((m) => (
            <Row
              key={m.id}
              label={t("account.payments.card")}
              note={
                <>
                  {t("account.payments.expires", { month: String(m.exp_month).padStart(2, "0"), year: String(m.exp_year).slice(-2) })}
                  {m.is_default && <> · {t("account.payments.default")}</>}
                </>
              }
              action={
                <span className="flex shrink-0 gap-4">
                  {!m.is_default && <button type="button" onClick={() => void act(m, "default")} className={link}>{t("account.payments.make_default")}</button>}
                  <button type="button" onClick={() => void act(m, "remove")} className={link}>{t("account.payments.remove")}</button>
                </span>
              }
            >
              {t("account.payments.ending", { brand: brandName(m.brand), last4: m.last4 })}
            </Row>
          ))}
        </div>
      )}
      {problem && <p role="alert" className="mt-3 text-label text-[#8C1D18]">{problem}</p>}
      {TEST_PROVIDER ? (
        adding ? (
          <AddCard onCancel={() => setAdding(false)} onDone={() => { setAdding(false); refresh(); }} />
        ) : (
          <button type="button" onClick={() => setAdding(true)} className={`${link} mt-[14px] inline-block font-bold`}>
            + {t("account.payments.add")}
          </button>
        )
      ) : (
        <p className="mt-[14px] text-small text-muted">{t("account.payments.live_note")}</p>
      )}
    </section>
  );
}
