"use client";
// R39: Settings > Monitoring: one test alert through every channel that is switched on (the Operations page,
// the paging webhook PAGING_WEBHOOK_URL, Sentry SENTRY_DSN), and which of them took it. Super admins only.
import { useState } from "react";

import { adminApi } from "@/lib/api";
import { apiMessage } from "@/lib/ops";

interface Result { paging: "sent" | "off" | "failed"; sentry: "sent" | "off" | "failed" }

const WORDS: Record<Result["paging"], string> = { sent: "sent", off: "off (not set)", failed: "failed: check the address and the logs" };

export function TestAlert() {
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState<Result | null>(null);
  const [err, setErr] = useState<string | null>(null);
  async function send() {
    setBusy(true);
    setErr(null);
    setOut(null);
    try {
      setOut((await adminApi.post<Result>("/user/ops/alerts/test")).data);
    } catch (e) {
      setErr(apiMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="space-y-3 rounded-2xl bg-white p-6" aria-label="Monitoring" data-testid="monitoring">
      <h2 className="m-0 text-h3">Monitoring</h2>
      <p className="m-0 text-small text-muted">Alerts show on the Operations page. Critical ones also page whoever is on call through the paging webhook (<code>PAGING_WEBHOOK_URL</code>), and errors go to Sentry (<code>SENTRY_DSN</code>). Both are set on Railway; see docs/launch/monitoring.md. Send a test after setting either.</p>
      <button type="button" onClick={() => void send()} disabled={busy} data-testid="send-test-alert"
        className="h-11 rounded-full bg-peacock px-5 font-bold text-white disabled:opacity-40">{busy ? "Sending…" : "Send test alert"}</button>
      {out ? (
        <ul role="status" className="m-0 list-none space-y-1 p-0 text-small" data-testid="test-alert-result">
          <li>Operations page: <b className="text-peacock">sent</b></li>
          <li>Paging webhook: <b className={out.paging === "sent" ? "text-peacock" : out.paging === "failed" ? "text-chili" : "text-muted"}>{WORDS[out.paging]}</b></li>
          <li>Sentry: <b className={out.sentry === "sent" ? "text-peacock" : out.sentry === "failed" ? "text-chili" : "text-muted"}>{WORDS[out.sentry]}</b></li>
        </ul>
      ) : null}
      {err ? <p role="alert" className="m-0 text-label text-chili">{err}</p> : null}
    </section>
  );
}
