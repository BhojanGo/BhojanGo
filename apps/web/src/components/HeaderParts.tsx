"use client";
// The header's interactive parts: country, language, address, search, account, bag.

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { api, useBag, useHydrated, useSession } from "@/lib/client";
import { useLanguage, usePrefs, useT } from "@/lib/i18n";
import { AddressBox } from "./AddressBox";
import { BagIcon, Chevron, Close, Globe, Pin, Search } from "./Icons";
import { MenuNote, MenuRow, MenuTitle, Popover } from "./Popover";

const pill = "flex h-11 shrink-0 items-center gap-2 rounded-full border border-[#E2E7E8] bg-white px-3 text-sm font-bold text-[#111418]";

export function CountryMenu({ countries, current }: { countries: { code: string; name: string }[]; current: { code: string; name: string } | null }) {
  const t = useT();
  const { setCountry } = usePrefs();
  if (!countries.length) return null;
  return (
    <Popover
      label={t("header.country_title")}
      button={(open, toggle) => (
        <button type="button" aria-label={t("header.country", { country: current?.name ?? "" })} aria-expanded={open} onClick={toggle} className={pill}>
          {current && <span className="rounded-[5px] bg-[#111418] px-[5px] py-[2px] text-[11px] font-extrabold text-white">{current.code}</span>}
          <span className="hidden lg:inline">{current?.name}</span>
          <Chevron color="#4C5A5E" />
        </button>
      )}
    >
      {(close) => (
        <>
          <MenuTitle>{t("header.country_title")}</MenuTitle>
          {countries.map((c) => (
            <MenuRow key={c.code} selected={c.code === current?.code} onClick={() => { close(); setCountry(c.code); }}>
              {c.name}
            </MenuRow>
          ))}
          <MenuNote>{t("header.country_note")}</MenuNote>
        </>
      )}
    </Popover>
  );
}

export function LanguageMenu({ compact }: { compact?: boolean }) {
  const t = useT();
  const { language, languages, country, name } = useLanguage();
  const { setLanguage } = usePrefs();
  const signedIn = useSession((s) => !!s.access);
  async function choose(lang: string) {
    setLanguage(lang);
    // Signed in: remember it on the account too (emails, SMS, the apps).
    const locale = `${lang}-${country?.code ?? "US"}`;
    if (signedIn) await api.core.PATCH("/api/v1/users/me", { body: { preferred_locale: locale as never } }).catch(() => undefined);
  }
  return (
    <Popover
      label={t("header.language")}
      button={(open, toggle) => (
        <button
          type="button"
          aria-label={t("header.language")}
          aria-expanded={open}
          onClick={toggle}
          className={`flex h-11 shrink-0 items-center gap-2 rounded-full px-[14px] text-sm font-bold text-[#111418] ${open ? "border-[1.5px] border-[#0B5D66] bg-[#EFF6F6]" : "border border-[#E2E7E8] bg-white"} ${compact ? "h-9 px-[10px] text-[13px] font-extrabold" : ""}`}
        >
          {compact ? (
            language.toUpperCase()
          ) : (
            <>
              <Globe color="#111418" />
              {name(language)}
              <Chevron color="#4C5A5E" />
            </>
          )}
        </button>
      )}
    >
      {(close) => (
        <>
          <MenuTitle>{t("header.language_title", { country: country?.name ?? "" })}</MenuTitle>
          {languages.map((l) => (
            <MenuRow key={l} selected={l === language} onClick={() => { close(); void choose(l); }}>
              <span lang={l}>{name(l)}</span>
            </MenuRow>
          ))}
          <MenuNote>{t("header.language_note")}</MenuNote>
        </>
      )}
    </Popover>
  );
}

export function AccountButton() {
  const t = useT();
  const hydrated = useHydrated();
  const user = useSession((s) => s.user);
  const signOut = useSession((s) => s.signOut);
  const router = useRouter();
  const path = usePathname();
  if (!hydrated || !user) {
    if (path.startsWith("/signin")) return null; // already on the sign-in page
    return (
      <Link
        href={`/signin?next=${encodeURIComponent(path)}`}
        className="flex h-11 shrink-0 items-center rounded-full border-[1.5px] border-[#C9D3D4] bg-white px-5 text-[15px] font-bold text-[#111418] hover:text-[#111418]"
      >
        {t("common.sign_in")}
      </Link>
    );
  }
  const initial = (user.full_name || user.email || "?").trim()[0]?.toUpperCase();
  return (
    <Popover
      label={t("header.account_menu")}
      width={220}
      button={(open, toggle) => (
        <button type="button" aria-label={t("common.your_account")} aria-expanded={open} onClick={toggle} className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[#DDEBEC] font-extrabold text-[#083F46]">
          {initial}
        </button>
      )}
    >
      {(close) => (
        <>
          <MenuRow href="/account/orders">{t("header.orders")}</MenuRow>
          <MenuRow href="/account/favourites">{t("header.favourites")}</MenuRow>
          <MenuRow href="/account/profile">{t("header.profile")}</MenuRow>
          <MenuRow onClick={async () => { close(); await signOut(); router.push("/"); router.refresh(); }}>{t("common.sign_out")}</MenuRow>
        </>
      )}
    </Popover>
  );
}

export function BagButton() {
  const t = useT();
  const hydrated = useHydrated();
  const count = useBag((s) => s.lines.reduce((n, l) => n + l.quantity, 0));
  const restaurant = useBag((s) => s.restaurant);
  if (!hydrated || !count) return null;
  return (
    <Link
      href="/checkout"
      aria-label={t("common.bag_count", { count })}
      title={restaurant?.name}
      className="flex h-11 shrink-0 items-center gap-2 rounded-full bg-[#111418] px-[18px] text-[15px] font-bold text-white hover:text-white"
    >
      <BagIcon color="#FFFFFF" />
      {t("common.bag_count", { count })}
    </Link>
  );
}

export function AddressPill({ label, country, mobile }: { label: string; country: string | null; mobile?: boolean }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  return (
    <>
      {mobile ? (
        <button type="button" onClick={() => setOpen(true)} aria-label={t("header.change_address")} className="flex min-w-0 flex-grow items-center gap-[10px] text-left">
          <Pin size={22} color="#0B5D66" />
          <span className="min-w-0">
            <span className="block text-xs text-[#4C5A5E]">{t("header.deliver_to", { place: "" }).trim()}</span>
            <b className="flex items-center gap-1 truncate text-[15px]">{label} <Chevron size={14} color="#4C5A5E" /></b>
          </span>
        </button>
      ) : (
        <button type="button" onClick={() => setOpen(true)} aria-label={t("header.change_address")} className="flex h-11 max-w-[260px] shrink-0 items-center gap-2 rounded-full border border-[#E2E7E8] bg-[#F4F6F6] px-4 text-sm font-bold text-[#111418]">
          <Pin size={16} color="#0B5D66" />
          <span className="truncate">{label}</span>
          <Chevron size={14} color="#4C5A5E" />
        </button>
      )}
      {open && (
        <div role="dialog" aria-modal="true" aria-label={t("header.change_address")} className="fixed inset-0 z-[60] flex items-start justify-center bg-[rgba(17,20,24,0.4)] p-4 pt-[10vh]" onClick={() => setOpen(false)}>
          <div className="w-full max-w-[560px] rounded-3xl bg-white p-6" onClick={(e) => e.stopPropagation()}>
            <div className="mb-4 flex items-center">
              <h2 className="m-0 flex-grow font-display text-[22px] font-semibold">{t("header.change_address")}</h2>
              <button type="button" aria-label={t("common.close")} onClick={() => setOpen(false)}><Close color="#4C5A5E" /></button>
            </div>
            <AddressBox size="sheet" country={country} autoFocus onPicked={() => setOpen(false)} />
          </div>
        </div>
      )}
    </>
  );
}

export function SearchBox({ cityPath, compact, placeholder }: { cityPath: string | null; compact?: boolean; placeholder?: string }) {
  const t = useT();
  const router = useRouter();
  const [q, setQ] = useState("");
  return (
    <form
      role="search"
      onSubmit={(e) => {
        e.preventDefault();
        router.push(`${cityPath ?? "/cities"}?q=${encodeURIComponent(q.trim())}`);
      }}
      className={`flex h-12 flex-grow items-center gap-[10px] rounded-full border border-[#E2E7E8] bg-[#F4F6F6] px-[18px] text-[15px] text-[#4C5A5E] ${compact ? "" : "min-w-0"}`}
    >
      <Search color="#4C5A5E" />
      <input aria-label={t("common.search_label")} value={q} onChange={(e) => setQ(e.target.value)} placeholder={placeholder ?? t("common.search_placeholder")} className="min-w-0 flex-grow bg-transparent text-[#111418] outline-none placeholder:text-[#4C5A5E]" />
    </form>
  );
}
