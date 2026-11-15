"use client";
// WebProfile: your details, language and country, addresses, payment methods,
// notifications, and your data (download, delete). Everything shown is your
// account's data; the country is the one your delivery address is in.

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { authed, useSession, type User } from "@/lib/client";
import { useLanguage, usePrefs, useT } from "@/lib/i18n";
import { saveFile } from "@/components/account/shared";
import { Addresses } from "./Addresses";
import { Payments } from "./Payments";
import { card, ghost, h2, input, link, primary, Row } from "./ui";

function Details({ user }: { user: User }) {
  const t = useT();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(user.full_name);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setMsg(null);
    try {
      const me = await authed<User>("PATCH", "/api/v1/users/me", { full_name: name.trim() });
      useSession.setState({ user: me });
      setEditing(false);
      setMsg(t("account.profile.saved"));
    } catch {
      setMsg(t("account.profile.save_failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="details" className={card}>
      <h2 id="details" className={h2}>{t("account.profile.details")}</h2>
      {editing ? (
        <form onSubmit={save} className="flex flex-wrap items-end gap-3 border-b border-[#EEF1F1] py-4">
          <label className="min-w-[220px] flex-grow text-label text-[#4C5A5E]">
            {t("account.profile.name_label")}
            <input value={name} onChange={(e) => setName(e.target.value)} maxLength={100} required autoFocus autoComplete="name" className={input} />
          </label>
          <button type="submit" disabled={busy} className={primary}>{t("common.save")}</button>
          <button type="button" onClick={() => { setEditing(false); setName(user.full_name); }} className={ghost}>{t("common.cancel")}</button>
        </form>
      ) : (
        <Row
          label={t("account.profile.name")}
          action={<button type="button" onClick={() => { setName(user.full_name); setEditing(true); setMsg(null); }} className={link}>{t("common.edit")}</button>}
        >
          {user.full_name}
        </Row>
      )}
      <Row label={t("account.profile.mobile")} note={user.is_phone_verified ? t("account.profile.mobile_note") : t("account.profile.mobile_unverified")}>
        {user.phone ?? t("account.profile.not_set")}
      </Row>
      <Row label={t("account.profile.email")} note={t("account.profile.email_note")}>
        {user.email ?? t("account.profile.not_set")}
      </Row>
      <p className="pt-3 text-small text-[#4C5A5E]">{t("account.profile.read_only_note")}</p>
      {msg && <p role="status" className="pt-2 text-label text-[#0B5D66]">{msg}</p>}
    </section>
  );
}

function LanguageCountry() {
  const t = useT();
  const { language, languages, country, name } = useLanguage();
  const { setLanguage } = usePrefs();
  const [open, setOpen] = useState(false);

  async function choose(lang: string) {
    setOpen(false);
    setLanguage(lang);
    // Remember it on the account too (emails, SMS, the apps), as the header's menu does.
    if (country) await authed("PATCH", "/api/v1/users/me", { preferred_locale: `${lang}-${country.code}` }).catch(() => undefined);
  }

  return (
    <section aria-labelledby="language" className={card}>
      <h2 id="language" className={h2}>{t("account.profile.language_country")}</h2>
      <Row
        label={t("account.profile.language")}
        note={t("account.profile.language_note")}
        action={
          languages.length > 1 && (
            <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)} className={link}>
              {t("account.profile.change")}
            </button>
          )
        }
      >
        <span lang={language}>{name(language)}</span>
      </Row>
      {open && (
        <div role="group" aria-label={t("account.profile.language")} className="flex flex-wrap gap-2 border-b border-[#EEF1F1] py-4">
          {languages.map((l) => (
            <button
              key={l}
              type="button"
              aria-pressed={l === language}
              onClick={() => void choose(l)}
              className={`flex h-10 items-center rounded-full px-4 text-label ${l === language ? "bg-[#111418] text-white" : "border border-[#C9D3D4] text-[#111418]"}`}
            >
              <span lang={l}>{name(l)}</span>
            </button>
          ))}
        </div>
      )}
      {country && (
        <Row label={t("account.profile.country")} note={t("account.profile.country_note")}>
          {country.name}
        </Row>
      )}
    </section>
  );
}

const KINDS = ["orders", "account", "offers"] as const;
const CHANNELS = ["push", "sms", "email"] as const;
type Prefs = Record<(typeof KINDS)[number], Record<(typeof CHANNELS)[number], boolean>>;

function Notifications() {
  const t = useT();
  const [prefs, setPrefs] = useState<Prefs | null | "error">(null);
  useEffect(() => {
    let live = true;
    authed<Prefs>("GET", "/api/v1/me/notification-preferences")
      .then((p) => live && setPrefs(p))
      .catch(() => live && setPrefs("error"));
    return () => {
      live = false;
    };
  }, []);

  async function flip(kind: (typeof KINDS)[number], channel: (typeof CHANNELS)[number]) {
    if (!prefs || prefs === "error") return;
    const before = prefs;
    const value = !prefs[kind][channel];
    setPrefs({ ...prefs, [kind]: { ...prefs[kind], [channel]: value } }); // optimistic
    try {
      setPrefs(await authed<Prefs>("PUT", "/api/v1/me/notification-preferences", { [kind]: { [channel]: value } }));
    } catch {
      setPrefs(before);
    }
  }

  return (
    <section id="notifications" aria-labelledby="notifications-title" className={card}>
      <h2 id="notifications-title" className={h2}>{t("account.notifications.title")}</h2>
      {prefs === null && <p role="status" className="mt-3 text-[#4C5A5E]">{t("account.loading")}</p>}
      {prefs === "error" && <p className="mt-3 text-[#4C5A5E]">{t("account.notifications.unavailable")}</p>}
      {prefs && prefs !== "error" && (
        <div role="table" aria-labelledby="notifications-title" className="mt-3">
          <div role="row" className="grid grid-cols-[1fr_repeat(3,56px)] text-center text-caption text-[#4C5A5E] md:grid-cols-[1fr_repeat(3,80px)]">
            <span role="columnheader" />
            {CHANNELS.map((c) => <span key={c} role="columnheader">{t(`account.notifications.${c}`)}</span>)}
          </div>
          {KINDS.map((k) => (
            <div key={k} role="row" className="grid grid-cols-[1fr_repeat(3,56px)] items-center border-b border-[#EEF1F1] py-[14px] md:grid-cols-[1fr_repeat(3,80px)]">
              <span role="rowheader">
                <b className="text-label">{t(`account.notifications.${k}`)}</b>
                <span className="block text-small text-[#4C5A5E]">{t(`account.notifications.${k}_note`)}</span>
              </span>
              {CHANNELS.map((c) => {
                const on = prefs[k]?.[c] ?? false;
                return (
                  <span key={c} role="cell" className="flex justify-center">
                    <button
                      type="button"
                      role="switch"
                      aria-checked={on}
                      aria-label={t("account.notifications.toggle", { kind: t(`account.notifications.${k}`), channel: t(`account.notifications.${c}`) })}
                      onClick={() => void flip(k, c)}
                      className={`relative h-7 w-12 shrink-0 rounded-full transition-colors ${on ? "bg-[#0B5D66]" : "bg-[#C9D3D4]"}`}
                    >
                      <span className={`absolute top-[3px] h-[22px] w-[22px] rounded-full bg-white transition-all ${on ? "left-[23px]" : "left-[3px]"}`} />
                    </button>
                  </span>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function Privacy() {
  const t = useT();
  const router = useRouter();
  const [busy, setBusy] = useState<"export" | "delete" | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!confirming) return;
    cancelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setConfirming(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [confirming]);

  async function exportData() {
    setBusy("export");
    setProblem(null);
    try {
      const data = await authed<unknown>("GET", "/api/v1/me/export");
      const blob = data instanceof Blob ? data : new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      saveFile(blob, "bhojango-data.json");
    } catch {
      setProblem(t("account.privacy.failed"));
    } finally {
      setBusy(null);
    }
  }

  async function deleteAccount() {
    setBusy("delete");
    setProblem(null);
    try {
      await authed("DELETE", "/api/v1/users/me");
      // The tokens are already dead on the server: forget them here too.
      useSession.setState({ access: null, refreshToken: null, user: null });
      router.push("/");
      router.refresh();
    } catch {
      setProblem(t("account.privacy.failed"));
      setBusy(null);
      setConfirming(false);
    }
  }

  return (
    <section id="privacy" aria-labelledby="privacy-title" className={card}>
      <h2 id="privacy-title" className={h2}>{t("account.privacy.title")}</h2>
      <div className="mt-4 flex flex-wrap gap-[10px]">
        <button type="button" onClick={exportData} disabled={busy !== null} className={`${ghost} h-12`}>
          {busy === "export" ? t("account.privacy.downloading") : t("account.privacy.download")}
        </button>
        <button type="button" onClick={() => setConfirming(true)} disabled={busy !== null} className="flex h-12 items-center rounded-full border-[1.5px] border-[#F1C9C4] px-5 font-bold text-[#B3261E] hover:bg-[#FCE8E6] disabled:opacity-60">
          {t("account.privacy.delete")}
        </button>
      </div>
      <p className="mt-4 text-small text-[#4C5A5E]">{t("account.privacy.note")}</p>
      {problem && <p role="alert" className="mt-2 text-label text-[#8C1D18]">{problem}</p>}

      {confirming && (
        <div className="fixed inset-0 z-[60] flex items-end justify-center bg-[rgba(17,20,24,0.45)] p-4 md:items-center" onMouseDown={(e) => e.target === e.currentTarget && setConfirming(false)}>
          <div role="alertdialog" aria-modal="true" aria-labelledby="delete-title" aria-describedby="delete-body" className="w-full max-w-[480px] rounded-3xl bg-white p-6 shadow-[0_16px_40px_rgba(17,20,24,0.16)]">
            <h3 id="delete-title" className="text-h2">{t("account.privacy.confirm_title")}</h3>
            <p id="delete-body" className="mt-3 text-body text-[#24383B]">{t("account.privacy.confirm_body")}</p>
            <div className="mt-6 flex flex-wrap justify-end gap-[10px]">
              <button ref={cancelRef} type="button" onClick={() => setConfirming(false)} disabled={busy === "delete"} className={ghost}>
                {t("common.cancel")}
              </button>
              <button type="button" onClick={deleteAccount} disabled={busy === "delete"} className="flex h-11 items-center rounded-full bg-[#B3261E] px-5 font-bold text-white hover:bg-[#8C1D18] disabled:opacity-60">
                {busy === "delete" ? t("account.privacy.deleting") : t("account.privacy.confirm")}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

export function ProfileView() {
  const t = useT();
  const user = useSession((s) => s.user);
  if (!user) return null; // the account frame sends you to sign in
  return (
    <div className="flex flex-col gap-5">
      <h1 className="text-h1 tracking-[-0.8px]">{t("account.profile.title")}</h1>
      <Details key={user.id} user={user} />
      <LanguageCountry />
      <Addresses />
      <Payments />
      <Notifications />
      <Privacy />
    </div>
  );
}
