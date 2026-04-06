"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";

import { useAuthStore } from "@/store/auth";
import { useCartStore } from "@/store/cart";

export default function Navbar() {
  const t = useTranslations("nav");
  const pathname = usePathname();
  const { isAuthenticated } = useAuthStore();
  const itemCount = useCartStore((s) => s.getItemCount());

  return (
    <nav className="sticky top-0 z-40 bg-white border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="text-xl font-bold text-brand-500">
          BhojanGo
        </Link>

        {/* Desktop nav */}
        <div className="hidden md:flex items-center gap-6">
          <NavLink href="/restaurants" label={t("restaurants")} active={pathname.startsWith("/restaurants")} />
          {isAuthenticated && (
            <>
              <NavLink href="/orders" label={t("orders")} active={pathname.startsWith("/orders")} />
              <NavLink href="/wallet" label={t("wallet")} active={pathname === "/wallet"} />
            </>
          )}
        </div>

        {/* Right actions */}
        <div className="flex items-center gap-3">
          {/* Cart */}
          <Link
            href="/cart"
            className="relative p-2 rounded-full hover:bg-gray-100 transition"
            aria-label="Cart"
          >
            <svg className="w-5 h-5 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z"
              />
            </svg>
            {itemCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 w-4.5 h-4.5 text-xs bg-brand-500 text-white rounded-full flex items-center justify-center font-bold leading-none px-1">
                {itemCount}
              </span>
            )}
          </Link>

          {isAuthenticated ? (
            <Link
              href="/profile"
              className="w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center text-brand-600 font-semibold text-sm hover:bg-brand-200 transition"
            >
              P
            </Link>
          ) : (
            <div className="flex items-center gap-2">
              <Link
                href="/login"
                className="text-sm font-medium text-gray-700 hover:text-brand-500 transition"
              >
                {t("login")}
              </Link>
              <Link
                href="/signup"
                className="text-sm font-semibold px-4 py-1.5 bg-brand-500 text-white rounded-lg hover:bg-brand-600 transition"
              >
                {t("signup")}
              </Link>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}

function NavLink({ href, label, active }: { href: string; label: string; active: boolean }) {
  return (
    <Link
      href={href}
      className={`text-sm font-medium transition ${
        active ? "text-brand-500" : "text-gray-600 hover:text-gray-900"
      }`}
    >
      {label}
    </Link>
  );
}
