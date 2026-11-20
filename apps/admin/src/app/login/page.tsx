"use client";
// Admin sign-in (round 8, D5): email + password, then the second step, which every admin
// account needs: a 6-digit code from an authenticator app, or one of the 10 recovery codes.
// The first time (no authenticator yet): a code to the admin's email, then the QR code and
// the key, then a code from the app; the recovery codes are shown once, to be saved.
import { useRouter } from "next/navigation";
import { useId, useState } from "react";

import { adminApi } from "@/lib/api";
import { useAdminAuth, type User } from "@/store/auth";
import { Logo } from "@bhojango/ui";

type Step = "password" | "totp" | "recovery" | "enrol-email" | "enrol-app" | "codes";
interface Tokens { access_token: string; refresh_token: string; user: User; admin_roles?: string[]; recovery_codes?: string[] }
interface Challenge { mfa_required: true; mfa_token: string; enrolment_required: boolean; email_code_sent: boolean }
interface Enrol { account: string; secret: string; otpauth_uri: string; qr_svg: string }

const field = "mt-1 block h-12 w-full rounded-2xl border-[1.5px] border-line-strong px-4 font-normal outline-none focus:border-peacock";
const primary = "h-12 w-full rounded-full bg-peacock font-bold text-white hover:bg-peacock-dark disabled:opacity-60";
const quiet = "min-h-[44px] text-label font-bold text-peacock underline-offset-4 hover:underline";

const ADMIN_PERSONAS = ["admin", "super_admin"];

function messageFor(err: unknown): string {
  const r = (err as { response?: { status?: number; data?: { detail?: { code?: string; retry_after?: number } | string } } }).response;
  const d = typeof r?.data?.detail === "object" ? r.data.detail : undefined;
  switch (d?.code) {
    case "INVALID_CREDENTIALS": return "That email and password don't match.";
    case "ACCOUNT_LOCKED": return `Too many tries. Try again in ${Math.max(1, Math.ceil((d.retry_after ?? 900) / 60))} minutes.`;
    case "CODE_INVALID": return "That code didn't work. Check the app shows the right account and try again.";
    case "MFA_EXPIRED": return "Your sign-in timed out. Start again with your password.";
    case "ACCOUNT_INACTIVE": return "This account is closed.";
    default:
      if (r?.status === 429) return "Too many tries. Wait a few minutes and try again.";
      return r ? "Something went wrong. Try again." : "Can't reach the server. Check your connection and try again.";
  }
}

/** The key in groups of four, easier to type into an app. */
const grouped = (key: string) => key.replace(/(.{4})/g, "$1 ").trim();

export default function AdminLoginPage() {
  const router = useRouter();
  const { login } = useAdminAuth();
  const [step, setStepRaw] = useState<Step>("password");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [code, setCode] = useState("");
  const [enrol, setEnrol] = useState<Enrol | null>(null);
  const [done, setDone] = useState<Tokens | null>(null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const codeId = useId();
  const errorId = useId();

  /** Each step starts with an empty code box; ``keepError`` keeps the message that sent us there. */
  function setStep(next: Step, keepError = false) {
    setStepRaw(next);
    setCode("");
    if (!keepError) setError("");
  }

  function finish(tokens: Tokens) {
    // Admin rights are role assignments ("role@scope"), or the admin persona.
    if (!tokens.admin_roles?.length && !ADMIN_PERSONAS.includes(tokens.user.role)) {
      setStep("password");
      setError("This account has no access to the admin console.");
      return;
    }
    login(tokens.user); // the session itself is in httpOnly cookies (R22 S8)
    router.push("/overview");
  }

  async function call<T>(path: string, body: unknown): Promise<T | null> {
    setError("");
    setLoading(true);
    try {
      return (await adminApi.post(path, body)).data as T;
    } catch (err) {
      const expired = (err as { response?: { data?: { detail?: { code?: string } } } }).response?.data?.detail?.code === "MFA_EXPIRED";
      setError(messageFor(err));
      if (expired) setStep("password", true);
      return null;
    } finally {
      setLoading(false);
    }
  }

  async function submitPassword(e: React.FormEvent) {
    e.preventDefault();
    const data = await call<Tokens | Challenge>("/user/auth/login", { email, password });
    if (!data) return;
    if ("mfa_required" in data && data.mfa_required) {
      setChallenge(data);
      setStep(data.enrolment_required ? "enrol-email" : "totp");
      return;
    }
    finish(data as Tokens);
  }

  async function submitCode(e: React.FormEvent) {
    e.preventDefault();
    if (!challenge) return;
    if (step === "totp") {
      const data = await call<Tokens>("/user/auth/mfa/verify", { mfa_token: challenge.mfa_token, code: code.replace(/\s/g, "") });
      if (data) finish(data);
    } else if (step === "recovery") {
      const data = await call<Tokens>("/user/auth/mfa/recovery", { mfa_token: challenge.mfa_token, recovery_code: code.trim() });
      if (data) finish(data);
    } else if (step === "enrol-email") {
      const data = await call<Enrol>("/user/auth/mfa/enrol/start", { mfa_token: challenge.mfa_token, email_code: code.replace(/\s/g, "") });
      if (data) {
        setEnrol(data);
        setStep("enrol-app");
      }
    } else if (step === "enrol-app") {
      const data = await call<Tokens>("/user/auth/mfa/enrol/confirm", { mfa_token: challenge.mfa_token, code: code.replace(/\s/g, "") });
      if (data) {
        setDone(data);
        setStep("codes");
      }
    }
  }

  function downloadCodes() {
    if (!done?.recovery_codes) return;
    const text = `BhojanGo admin recovery codes for ${done.user.email ?? email}\nEach works once. Keep them somewhere safe.\n\n${done.recovery_codes.join("\n")}\n`;
    const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "bhojango-admin-recovery-codes.txt";
    a.click();
    URL.revokeObjectURL(url);
  }

  const back = (
    <button type="button" onClick={() => { setStep("password"); setChallenge(null); setPassword(""); }} className={quiet}>
      ← Use a different account
    </button>
  );
  const errorLine = error && <p id={errorId} role="alert" className="text-label text-chili">{error}</p>;
  const sixDigits = (label: string, hint: string) => (
    <label htmlFor={codeId} className="block text-label">{label}
      <input id={codeId} inputMode="numeric" autoComplete="one-time-code" autoFocus required maxLength={7} value={code}
        onChange={(e) => setCode(e.target.value.replace(/[^\d ]/g, ""))} aria-describedby={error ? errorId : undefined}
        className={`${field} tracking-[0.3em]`} />
      <span className="mt-1 block text-small font-normal text-muted">{hint}</span>
    </label>
  );

  return (
    <main className="flex min-h-screen items-center justify-center bg-peacock-wash px-4 py-10 font-sans text-kohl">
      <div className={step === "enrol-app" || step === "codes" ? "w-full max-w-md" : "w-full max-w-sm"}>
        <div className="mb-8 flex justify-center"><Logo size={36} suffix="admin" /></div>
        <div className="space-y-5 rounded-3xl bg-white p-8 shadow-[0_8px_24px_rgba(17,20,24,0.08)]">
          {step === "password" && (
            <form onSubmit={submitPassword} className="space-y-5">
              <h1 className="m-0 text-h2">Sign in</h1>
              <label className="block text-label">Email
                <input type="email" required autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)}
                  className={field} placeholder="you@bhojango.com" />
              </label>
              <label className="block text-label">Password
                <input type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)}
                  className={field} />
              </label>
              {errorLine}
              <button type="submit" disabled={loading} className={primary}>{loading ? "Signing in…" : "Sign in"}</button>
              <p className="m-0 text-small text-muted">Next you&apos;ll confirm it&apos;s you with your authenticator app.</p>
            </form>
          )}

          {(step === "totp" || step === "recovery") && (
            <form onSubmit={submitCode} className="space-y-5">
              {back}
              <h1 className="m-0 text-h2">{step === "totp" ? "Enter your authenticator code" : "Use a recovery code"}</h1>
              {step === "totp"
                ? sixDigits("6-digit code", "Open your authenticator app and enter the code it shows for BhojanGo.")
                : (
                  <label htmlFor={codeId} className="block text-label">Recovery code
                    <input id={codeId} autoComplete="off" autoCapitalize="characters" spellCheck={false} autoFocus required maxLength={24}
                      value={code} onChange={(e) => setCode(e.target.value)} className={`${field} font-mono uppercase`} placeholder="XXXXX-XXXXX" />
                    <span className="mt-1 block text-small font-normal text-muted">One of the codes you saved when you set up two-step sign-in. Each works once.</span>
                  </label>
                )}
              {errorLine}
              <button type="submit" disabled={loading || (step === "totp" ? code.replace(/\s/g, "").length !== 6 : code.trim().length < 8)} className={primary}>
                {loading ? "Checking…" : "Continue"}
              </button>
              <button type="button" onClick={() => setStep(step === "totp" ? "recovery" : "totp")} className={quiet}>
                {step === "totp" ? "Can't use your app? Use a recovery code" : "Use your authenticator app instead"}
              </button>
            </form>
          )}

          {step === "enrol-email" && (
            <form onSubmit={submitCode} className="space-y-5">
              {back}
              <h1 className="m-0 text-h2">Set up two-step sign-in</h1>
              <p className="m-0 text-body text-muted">
                Every admin account signs in with a code from an authenticator app (Google Authenticator, Microsoft
                Authenticator, 1Password and others). First, confirm it&apos;s you: we emailed a 6-digit code to {email}.
              </p>
              {sixDigits("Code from the email", "It works for 10 minutes. Not there? Look in spam, or start again to get a new one.")}
              {errorLine}
              <button type="submit" disabled={loading || code.replace(/\s/g, "").length !== 6} className={primary}>{loading ? "Checking…" : "Continue"}</button>
            </form>
          )}

          {step === "enrol-app" && enrol && (
            <form onSubmit={submitCode} className="space-y-5">
              <h1 className="m-0 text-h2">Add BhojanGo to your authenticator app</h1>
              <ol className="m-0 space-y-4 pl-5 text-body">
                <li>
                  Scan this QR code with the app.
                  {/* eslint-disable-next-line @next/next/no-img-element -- an SVG data URI made by the API */}
                  <img src={enrol.qr_svg} alt={`QR code to add ${enrol.account} to an authenticator app`} width={200} height={200}
                    className="mt-3 block rounded-xl border border-line p-2" />
                </li>
                <li>
                  Can&apos;t scan? Enter this key in the app (time-based):
                  <code className="mt-2 block select-all break-all rounded-xl bg-peacock-wash px-3 py-2 font-mono text-label">{grouped(enrol.secret)}</code>
                </li>
                <li>{sixDigits("Code from the app", "Enter the 6-digit code the app now shows for BhojanGo.")}</li>
              </ol>
              {errorLine}
              <button type="submit" disabled={loading || code.replace(/\s/g, "").length !== 6} className={primary}>{loading ? "Checking…" : "Turn on two-step sign-in"}</button>
            </form>
          )}

          {step === "codes" && done?.recovery_codes && (
            <div className="space-y-5">
              <h1 className="m-0 text-h2">Save your recovery codes</h1>
              <p className="m-0 text-body text-muted">
                If you lose your phone, each of these codes signs you in once. This is the only time they are shown:
                keep them in a password manager or somewhere safe offline.
              </p>
              <ul aria-label="Recovery codes" className="m-0 grid list-none grid-cols-2 gap-2 rounded-2xl bg-peacock-wash p-4 font-mono text-label">
                {done.recovery_codes.map((c) => <li key={c}>{c}</li>)}
              </ul>
              <div className="flex flex-wrap gap-3">
                <button type="button" onClick={() => void navigator.clipboard?.writeText(done.recovery_codes?.join("\n") ?? "")}
                  className="h-11 rounded-full border-[1.5px] border-line-strong px-5 font-bold hover:bg-peacock-wash">Copy</button>
                <button type="button" onClick={downloadCodes}
                  className="h-11 rounded-full border-[1.5px] border-line-strong px-5 font-bold hover:bg-peacock-wash">Download .txt</button>
              </div>
              <label className="flex items-start gap-3 text-body">
                <input type="checkbox" checked={saved} onChange={(e) => setSaved(e.target.checked)} className="mt-1 h-5 w-5 accent-peacock" />
                I&apos;ve saved these codes somewhere safe.
              </label>
              <button type="button" disabled={!saved} onClick={() => finish(done)} className={primary}>Continue to the console</button>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
