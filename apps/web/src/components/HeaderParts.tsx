"use client";
// The header's interactive parts: language, address, search, account, bag.

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useState } from "react";

import { api, useBag, useHydrated, useSession } from "@/lib/client";
import { useLanguage, usePrefs, useT } from "@/lib/i18n";
import { AddressDialog } from "./AddressDialog";
import { BagIcon, Chevron, Globe, Pin, Search } from "./Icons";
import { MenuRow, Popover } from "./Popover";

/**
 * The language pill (R6, like Uber's): a globe and the language's code ("EN", "HI",
 * "TE"). It opens a small list anchored to it (on a phone too: no sheet) of the
 * country's languages, each in its own script. The choice is a cookie (bg_lang), so
 * the server renders it and it survives reloads.
 */
export function LanguageMenu() {
  const t = useT();
  const { language, list, country, name } = useLanguage();
  const { setLanguage } = usePrefs();
  const signedIn = useSession((s) => s.signedIn);
  async function choose(lang: string) {
    setLanguage(lang);
    // Signed in: remember it on the account too (emails, SMS, the apps).
    const locale = `${lang}-${country?.code ?? "US"}`;
    if (signedIn) await api.core.PATCH("/api/v1/users/me", { body: { preferred_locale: locale as never } }).catch(() => undefined);
  }
  return (
    <Popover
      label={t("header.language")}
      width={200}
      button={(open, toggle) => (
        <button
          type="button"
          aria-label={t("header.language_pill", { language: name(language) })}
          aria-expanded={open}
          aria-haspopup="menu"
          onClick={toggle}
          data-testid="language-pill"
          className={`flex h-9 shrink-0 items-center gap-[6px] rounded-full px-3 text-label text-[#111418] md:h-10 ${open ? "border-[1.5px] border-[#0B5D66] bg-[#EFF6F6]" : "border border-[#E2E7E8] bg-white"}`}
        >
          <Globe size={18} color="#111418" />
          <span>{language.toUpperCase()}</span>
        </button>
      )}
    >
      {(close) => (
        <>
          {list.map((l) => (
            <MenuRow key={l.code} selected={l.code === language} onClick={() => { close(); void choose(l.code); }}>
              <span lang={l.code}>{l.name}</span>
            </MenuRow>
          ))}
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
        className="flex h-11 shrink-0 items-center rounded-full border-[1.5px] border-[#C9D3D4] bg-white px-5 text-label text-[#111418] hover:text-[#111418]"
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
        <button type="button" aria-label={t("common.your_account")} aria-expanded={open} onClick={toggle} className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[#DDEBEC] font-bold text-[#083F46]">
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
      className="flex h-11 shrink-0 items-center gap-2 rounded-full bg-[#111418] px-[18px] text-label text-white hover:text-white"
    >
      <BagIcon color="#FFFFFF" />
      {t("common.bag_count", { count })}
    </Link>
  );
}

export function AddressPill({ label, country, mobile, inline }: { label: string; country: string | null; mobile?: boolean; inline?: boolean }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  return (
    <>
      {inline ? (
        <button type="button" onClick={() => setOpen(true)} aria-label={t("header.change_address")} data-testid="change-address"
          className="inline font-semibold text-[#0B5D66] underline decoration-[#0B5D66]/40 underline-offset-2">
          {label}
        </button>
      ) : mobile ? (
        <button type="button" onClick={() => setOpen(true)} aria-label={t("header.change_address")} className="flex min-w-0 flex-grow items-center gap-[10px] text-left">
          <Pin size={22} color="#0B5D66" />
          <span className="min-w-0">
            <span className="block text-small text-muted">{t("header.deliver_to", { place: "" }).trim()}</span>
            <b className="flex items-center gap-1 truncate text-label">{label} <Chevron size={14} color="#3D4A4E" /></b>
          </span>
        </button>
      ) : (
        <button type="button" onClick={() => setOpen(true)} aria-label={t("header.change_address")} className="flex h-11 max-w-[260px] shrink-0 items-center gap-2 rounded-full border border-[#E2E7E8] bg-[#F4F6F6] px-4 text-label text-[#111418]">
          <Pin size={16} color="#0B5D66" />
          <span className="truncate">{label}</span>
          <Chevron size={14} color="#3D4A4E" />
        </button>
      )}
      {open && <AddressDialog title={t("header.change_address")} country={country} onClose={close} />}
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
      className={`flex h-12 flex-grow items-center gap-[10px] rounded-full border border-[#E2E7E8] bg-[#F4F6F6] px-[18px] text-body text-muted ${compact ? "" : "min-w-0"}`}
    >
      <Search color="#3D4A4E" />
      <input aria-label={t("common.search_label")} value={q} onChange={(e) => setQ(e.target.value)} placeholder={placeholder ?? t("common.search_placeholder")} className="min-w-0 flex-grow bg-transparent text-[#111418] outline-none placeholder:text-muted" />
    </form>
  );
}
