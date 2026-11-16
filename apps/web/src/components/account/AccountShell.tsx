"use client";
// The account pages' frame (WebOrders, WebFavourites, WebProfile): who is
// signed in, the account navigation, and the page. Signed out → sign in and
// come back. Phone: the navigation is a scrolling row above the page.

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useHydrated, useSession } from "@/lib/client";
import { useT } from "@/lib/i18n";

const NAV = [
  { key: "orders", href: "/account/orders", match: "/account/orders" },
  { key: "addresses", href: "/account/profile#addresses" },
  { key: "payments", href: "/account/profile#payments" },
  { key: "favourites", href: "/account/favourites", match: "/account/favourites" },
  { key: "profile", href: "/account/profile", match: "/account/profile" },
  { key: "notifications", href: "/account/profile#notifications" },
  { key: "privacy", href: "/account/profile#privacy" },
  { key: "help", href: "/help" },
] as const;

export function AccountShell({ children }: { children: ReactNode }) {
  const t = useT();
  const hydrated = useHydrated();
  const user = useSession((s) => s.user);
  const signOut = useSession((s) => s.signOut);
  const router = useRouter();
  const path = usePathname();

  useEffect(() => {
    if (hydrated && !user) router.replace(`/signin?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
  }, [hydrated, user, router]);

  if (!hydrated || !user) {
    return (
      <div className="container-page py-16 text-muted" role="status">
        {t("account.loading")}
      </div>
    );
  }

  const initial = (user.full_name || user.email || "?").trim()[0]?.toUpperCase();
  return (
    <div className="flex container-page flex-col gap-5 pb-[72px] pt-5 md:flex-row md:gap-10 md:pt-8">
      <aside className="md:w-[260px] md:shrink-0">
        <div className="flex items-center gap-3 px-1 pb-4 md:pb-5 md:pt-1">
          <span aria-hidden="true" className="flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-full bg-[#DDEBEC] text-h3 text-[#083F46]">
            {initial}
          </span>
          <span className="min-w-0">
            <b className="block truncate text-h3">{user.full_name}</b>
            {user.phone && <span className="text-small text-muted">{user.phone}</span>}
          </span>
        </div>
        <nav aria-label={t("account.nav.label")} className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 md:mx-0 md:flex-col md:gap-[2px] md:overflow-visible md:px-0 md:pb-0">
          {NAV.map((n) => {
            const active = "match" in n && path.startsWith(n.match);
            return (
              <Link
                key={n.key}
                href={n.href}
                aria-current={active ? "page" : undefined}
                className={`flex h-10 shrink-0 items-center whitespace-nowrap rounded-full px-4 text-label md:h-12 md:rounded-xl ${
                  active
                    ? "bg-[#EFF6F6] font-bold text-[#083F46] hover:text-[#083F46]"
                    : "border border-[#E2E7E8] font-semibold text-[#111418] hover:bg-[#F4F6F6] hover:text-[#111418] md:border-0"
                }`}
              >
                {t(`account.nav.${n.key}`)}
              </Link>
            );
          })}
          <button
            type="button"
            onClick={async () => {
              await signOut();
              router.push("/");
              router.refresh();
            }}
            className="flex h-10 shrink-0 items-center whitespace-nowrap rounded-full px-4 text-label text-muted md:mt-4 md:h-12"
          >
            {t("account.nav.sign_out")}
          </button>
        </nav>
      </aside>
      <div className="min-w-0 flex-grow">{children}</div>
    </div>
  );
}
