"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { adminApi } from "@/lib/api";
import { useAdminAuth } from "@/store/auth";

export default function AdminLoginPage() {
  const router = useRouter();
  const { login } = useAdminAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await adminApi.post("/user/auth/login", { email, password });
      const allowedRoles = ["admin", "super_admin", "city_manager", "support"];
      if (!allowedRoles.includes(data.user.role)) {
        setError("You do not have access to the admin dashboard.");
        return;
      }
      login(data.access_token, data.refresh_token ?? null, data.user);
      router.push("/overview");
    } catch {
      setError("Invalid email or password.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-peacock-wash px-4 font-body text-kohl">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center justify-center gap-2.5 font-display text-2xl font-bold tracking-[-0.4px]">
          <svg width="34" height="34" viewBox="0 0 40 40" aria-hidden="true">
            <path d="M11 5.5v24" stroke="#0B5D66" strokeWidth="5" strokeLinecap="round" fill="none" />
            <circle cx="20.5" cy="25" r="8.5" fill="none" stroke="#0B5D66" strokeWidth="5" />
            <path d="M18.5 13.5c-1.6-1.8 1.6-3.4 0-5.6M24.5 13.5c-1.6-1.8 1.6-3.4 0-5.6" stroke="#D4932A" strokeWidth="2.2" strokeLinecap="round" fill="none" />
          </svg>
          bhojango <span className="font-body text-sm font-semibold tracking-normal text-muted">admin</span>
        </div>
        <form onSubmit={handleSubmit} className="space-y-5 rounded-3xl bg-white p-8 shadow-[0_8px_24px_rgba(17,20,24,0.08)]">
          <h1 className="m-0 font-display text-2xl font-semibold">Sign in</h1>
          <label className="block text-sm font-bold">Email
            <input type="email" required autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)}
              className="mt-1 block h-12 w-full rounded-2xl border-[1.5px] border-line-strong px-4 font-normal outline-none focus:border-peacock" placeholder="you@bhojango.com" />
          </label>
          <label className="block text-sm font-bold">Password
            <input type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)}
              className="mt-1 block h-12 w-full rounded-2xl border-[1.5px] border-line-strong px-4 font-normal outline-none focus:border-peacock" />
          </label>
          {error && <p role="alert" className="text-sm font-semibold text-chili">{error}</p>}
          <button type="submit" disabled={loading} className="h-12 w-full rounded-full bg-peacock font-extrabold text-white hover:bg-peacock-dark disabled:opacity-60">
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
