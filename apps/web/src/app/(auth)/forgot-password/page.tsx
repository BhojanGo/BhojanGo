"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";

type Step = "request" | "reset";

export default function ForgotPasswordPage() {
  const router = useRouter();

  const [step, setStep] = useState<Step>("request");
  const [phone, setPhone] = useState("");
  const [country, setCountry] = useState<"US" | "IN">("IN");
  const [otp, setOtp] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);

  function extractError(err: unknown, fallback: string): string {
    const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "message" in detail) {
      return String((detail as { message?: unknown }).message ?? fallback);
    }
    return fallback;
  }

  async function sendOtp(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setInfo("");
    setLoading(true);
    try {
      await api.post("/user/auth/send-otp", { phone, country });
      setInfo("We sent a 6-digit code to your phone.");
      setStep("reset");
    } catch (err: unknown) {
      setError(extractError(err, "Could not send the code. Please try again."));
    } finally {
      setLoading(false);
    }
  }

  async function resetPassword(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.post("/user/auth/reset-password", { phone, otp, new_password: newPassword });
      router.push("/login?reset=1");
    } catch (err: unknown) {
      setError(extractError(err, "Could not reset your password. Check the code and try again."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Link href="/" className="text-3xl font-bold text-emerald-500">
            BhojanGo
          </Link>
          <h1 className="mt-4 text-2xl font-semibold text-gray-900">Reset your password</h1>
          <p className="mt-1 text-gray-500">
            {step === "request"
              ? "Enter your phone number and we'll send you a verification code."
              : "Enter the code and choose a new password."}
          </p>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
          {step === "request" ? (
            <form onSubmit={sendOtp} className="space-y-5">
              <div>
                <label htmlFor="country" className="block text-sm font-medium text-gray-700 mb-1">
                  Country
                </label>
                <select
                  id="country"
                  value={country}
                  onChange={(e) => setCountry(e.target.value as "US" | "IN")}
                  className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none transition text-sm"
                >
                  <option value="IN">India (+91)</option>
                  <option value="US">United States (+1)</option>
                </select>
              </div>
              <div>
                <label htmlFor="phone" className="block text-sm font-medium text-gray-700 mb-1">
                  Phone number
                </label>
                <input
                  id="phone"
                  type="tel"
                  autoComplete="tel"
                  required
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none transition text-sm"
                  placeholder="+14155552671"
                />
              </div>

              {error && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 px-4 bg-emerald-500 hover:bg-emerald-700 disabled:opacity-60 text-white font-semibold rounded-lg transition text-sm"
              >
                {loading ? "..." : "Send code"}
              </button>
            </form>
          ) : (
            <form onSubmit={resetPassword} className="space-y-5">
              {info && <p className="text-sm text-emerald-700 bg-emerald-50 rounded-lg px-3 py-2">{info}</p>}
              <div>
                <label htmlFor="otp" className="block text-sm font-medium text-gray-700 mb-1">
                  Verification code
                </label>
                <input
                  id="otp"
                  inputMode="numeric"
                  pattern="\d{6}"
                  maxLength={6}
                  required
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
                  className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none transition text-sm tracking-widest"
                  placeholder="123456"
                />
              </div>
              <div>
                <label htmlFor="newPassword" className="block text-sm font-medium text-gray-700 mb-1">
                  New password
                </label>
                <input
                  id="newPassword"
                  type="password"
                  autoComplete="new-password"
                  required
                  minLength={8}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none transition text-sm"
                  placeholder="At least 8 chars, with upper, lower & a digit"
                />
              </div>

              {error && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 px-4 bg-emerald-500 hover:bg-emerald-700 disabled:opacity-60 text-white font-semibold rounded-lg transition text-sm"
              >
                {loading ? "..." : "Reset password"}
              </button>
              <button
                type="button"
                onClick={() => setStep("request")}
                className="w-full text-sm text-gray-500 hover:underline"
              >
                Use a different phone number
              </button>
            </form>
          )}
        </div>

        <p className="mt-6 text-center text-sm text-gray-500">
          Remembered it?{" "}
          <Link href="/login" className="text-emerald-500 font-semibold hover:underline">
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
