"use client";
// The phone tab bar (MWebHome): Home, Search, Orders, Account, fixed at the
// bottom on phones only, above the home indicator (safe area). Hidden where a
// page has its own bottom bar (a kitchen's bag, checkout's pay button, live
// tracking) and on sign-in. A spacer of the same height keeps the page's end
// (the footer) clear of it. Search opens the city's kitchen search (or the
// city directory's search without an address).
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { useT } from "@/lib/i18n";
import { HomeIcon, ReceiptIcon, Search, UserIcon } from "./Icons";

// Top-level routes that aren't a country (so "/{a}/{b}/{c}" with another first part is a kitchen page).
const STATIC = new Set(["account", "cities", "checkout", "credits", "help", "orders", "partner", "privacy", "ride", "signin", "terms"]);

type Tab = "home" | "search" | "orders" | "account";

function where(path: string): { hidden: boolean; tab: Tab | null } {
  const seg = path.split("/").filter(Boolean);
  const first = seg[0] ?? "";
  const kitchen = seg.length === 3 && !STATIC.has(first);
  const hidden = kitchen || first === "checkout" || first === "signin" || (first === "orders" && seg.length > 1) || (first === "account" && seg.at(-1) === "report");
  const tab: Tab | null = !seg.length
    ? "home"
    : first === "cities" || (seg.length === 2 && !STATIC.has(first))
      ? "search"
      : first === "account"
        ? seg[1] === "orders"
          ? "orders"
          : "account"
        : null;
  return { hidden, tab };
}

export function TabBar({ cityPath }: { cityPath: string | null }) {
  const t = useT();
  const path = usePathname() ?? "/";
  const { hidden, tab } = where(path);

  // Arriving from the Search tab: put the cursor in the search box.
  useEffect(() => {
    if (window.location.hash !== "#search") return;
    const box = document.querySelector<HTMLInputElement>("#search input");
    box?.focus({ preventScroll: true });
  }, [path]);

  if (hidden) return null;
  const tabs: { key: Tab; href: string; label: string; icon: React.ReactNode }[] = [
    { key: "home", href: "/", label: t("tabs.home"), icon: <HomeIcon /> },
    { key: "search", href: `${cityPath ?? "/cities"}#search`, label: t("tabs.search"), icon: <Search size={22} /> },
    { key: "orders", href: "/account/orders", label: t("tabs.orders"), icon: <ReceiptIcon /> },
    { key: "account", href: "/account/profile", label: t("tabs.account"), icon: <UserIcon /> },
  ];
  return (
    <>
      <div aria-hidden="true" className="h-[calc(64px+env(safe-area-inset-bottom))] md:hidden" />
      <nav aria-label={t("tabs.label")} className="fixed inset-x-0 bottom-0 z-40 border-t border-[#E2E7E8] bg-white pb-[env(safe-area-inset-bottom)] md:hidden">
        <ul className="m-0 grid h-16 list-none grid-cols-4 p-0">
          {tabs.map((x) => {
            const on = x.key === tab;
            return (
              <li key={x.key}>
                <Link
                  href={x.href}
                  aria-current={on ? "page" : undefined}
                  className={`flex h-full flex-col items-center justify-center gap-1 text-small ${on ? "text-[#0B5D66] hover:text-[#0B5D66]" : "text-[#4C5A5E] hover:text-[#111418]"}`}
                >
                  {x.icon}
                  {x.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </>
  );
}
