"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAdminAuth } from "@/store/auth";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: "📊", roles: ["admin", "super_admin", "city_manager", "support"] },
  { href: "/orders", label: "Orders", icon: "📦", roles: ["admin", "super_admin", "city_manager", "support"] },
  { href: "/restaurants", label: "Restaurants", icon: "🍽️", roles: ["admin", "super_admin", "city_manager"] },
  { href: "/users", label: "Users", icon: "👥", roles: ["admin", "super_admin"] },
  { href: "/drivers", label: "Drivers", icon: "🚴", roles: ["admin", "super_admin", "city_manager"] },
  { href: "/payments", label: "Payments", icon: "💳", roles: ["admin", "super_admin"] },
  { href: "/analytics", label: "Analytics", icon: "📈", roles: ["super_admin"] },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user, logout } = useAdminAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login");
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) return null;

  const visibleNavItems = NAV_ITEMS.filter((item) =>
    item.roles.includes(user?.role ?? "")
  );

  return (
    <div className="flex h-screen bg-gray-950 text-white overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 bg-gray-900 flex flex-col flex-shrink-0">
        <div className="px-5 py-5 border-b border-gray-800">
          <p className="text-lg font-bold text-emerald-600">BhojanGo</p>
          <p className="text-xs text-gray-500 mt-0.5">Admin Panel</p>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {visibleNavItems.map((item) => {
            const isActive = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
                  isActive
                    ? "bg-emerald-600/10 text-emerald-500"
                    : "text-gray-400 hover:bg-gray-800 hover:text-white"
                }`}
              >
                <span>{item.icon}</span>
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="px-5 py-4 border-t border-gray-800">
          <p className="text-sm font-medium text-white truncate">{user?.full_name}</p>
          <p className="text-xs text-gray-500 mt-0.5 capitalize">{user?.role?.replace("_", " ")}</p>
          <button
            onClick={() => {
              logout();
              router.push("/login");
            }}
            className="mt-3 text-xs text-gray-500 hover:text-red-400 transition"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto bg-gray-950">
        {children}
      </main>
    </div>
  );
}
