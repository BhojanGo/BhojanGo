"use client";
// Email sign-in on the website (round 8, D5): the API calls and the words for its answers.
// The API answers sign-up, "email me a code" and "forgot password" the same whether or
// not the email has an account, so these pages never say which it is either.
import { ApiError, unwrap } from "@bhojango/api-client";

import { api, useSession } from "@/lib/client";

type T = (key: string, vars?: Record<string, string | number>) => string;
type Tokens = { access_token: string; refresh_token: string };
type SignInAnswer = Tokens | { mfa_required: true };

/** The page's language (<html lang>): emails are written in it when the country offers it. */
function language(): string | undefined {
  const lang = typeof document === "undefined" ? "" : document.documentElement.lang;
  return /^[a-z]{2}$/.test(lang) ? lang : undefined;
}

export class AdminAccountError extends Error {}

async function adopt(answer: SignInAnswer): Promise<void> {
  // Admin accounts sign in on the admin console (their second step lives there).
  if ("mfa_required" in answer && answer.mfa_required) throw new AdminAccountError("admin");
  await useSession.getState().adopt(answer as Tokens);
}

export async function signInWithPassword(email: string, password: string): Promise<void> {
  await adopt(unwrap(await api.core.POST("/api/v1/auth/login", { body: { email, password } })) as SignInAnswer);
}

export async function signUp(email: string, password: string, country: string): Promise<void> {
  unwrap(await api.core.POST("/api/v1/auth/email/sign-up", { body: { email, password, country, language: language() } }));
}

export async function sendEmailCode(email: string): Promise<void> {
  unwrap(await api.core.POST("/api/v1/auth/email/code", { body: { email, language: language() } }));
}

export async function verifyEmailCode(email: string, code: string): Promise<void> {
  await adopt(unwrap(await api.core.POST("/api/v1/auth/email/verify", { body: { email, code } })) as SignInAnswer);
}

export async function forgotPassword(email: string): Promise<void> {
  unwrap(await api.core.POST("/api/v1/auth/password/forgot", { body: { email, language: language() } }));
}

export async function resetLinkWorks(token: string): Promise<boolean> {
  return unwrap(await api.core.POST("/api/v1/auth/password/reset/check", { body: { token } })).valid;
}

export async function resetPassword(token: string, newPassword: string): Promise<void> {
  unwrap(await api.core.POST("/api/v1/auth/password/reset", { body: { token, new_password: newPassword } }));
}

export const MIN_PASSWORD = 10;
export const looksLikeEmail = (s: string) => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(s.trim());

/** The API's answer in the visitor's words (never the raw message, never a stack trace). */
export function authError(err: unknown, t: T): string {
  if (err instanceof AdminAccountError) return t("auth.err_admin");
  const code = err instanceof ApiError ? err.code : undefined;
  const body = err instanceof ApiError ? (err.body as { detail?: { retry_after?: number } } | undefined) : undefined;
  switch (code) {
    case "INVALID_CREDENTIALS": return t("auth.err_invalid");
    case "ACCOUNT_LOCKED": return t("auth.err_locked", { minutes: Math.max(1, Math.ceil((body?.detail?.retry_after ?? 900) / 60)) });
    case "PASSWORD_TOO_SHORT": return t("auth.err_too_short");
    case "PASSWORD_TOO_LONG": return t("auth.err_too_long");
    case "PASSWORD_LIKE_EMAIL": return t("auth.err_like_email");
    case "PASSWORD_BREACHED": return t("auth.err_breached");
    case "CODE_INVALID": case "OTP_INVALID": return t("auth.err_code");
    case "TOO_MANY_EMAILS": case "TOO_MANY_REQUESTS": case "OTP_LIMIT_REACHED": return t("auth.err_too_many");
    case "RESET_LINK_INVALID": return t("auth.reset_invalid");
    case "ACCOUNT_INACTIVE": return t("auth.err_inactive");
    case "EMAIL_IN_USE": return t("account.security.err_email_in_use");
    case "PHONE_IN_USE": return t("account.security.err_phone_in_use");
    case "WRONG_PASSWORD": return t("account.security.err_wrong_password");
    case "EMAIL_REQUIRED": return t("account.security.err_email_required");
    case "ALREADY_LINKED": return t("account.security.err_already");
    case "COUNTRY_NOT_AVAILABLE": case "PHONE_COUNTRY_MISMATCH": return t("account.security.err_phone_country");
    default:
      if (err instanceof ApiError && err.status === 429) return t("auth.err_too_many");
      return t("auth.err_generic");
  }
}
