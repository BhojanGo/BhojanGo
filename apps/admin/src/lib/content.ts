/**
 * Content → Help (round 8, F9): help articles for the website, per country
 * ("*" = every country) and language. core_api /api/v1/ops/help.
 * content.view reads; content.edit writes and publishes (a country's articles:
 * its country manager; every country's: the super admin).
 */
import { useQuery } from "@tanstack/react-query";

import { adminApi } from "@/lib/api";

export const HELP_TOPICS = [
  { value: "orders", label: "Orders" },
  { value: "payments-refunds", label: "Payments and refunds" },
  { value: "delivery", label: "Delivery" },
  { value: "account", label: "Account and sign-in" },
  { value: "kitchen-partners", label: "Restaurant partners" },
  { value: "delivery-partners", label: "Delivery partners" },
] as const;
export const topicLabel = (v: string) => HELP_TOPICS.find((t) => t.value === v)?.label ?? v;

/** Article languages (the website's: packages/i18n), in their own script. */
export const HELP_LANGUAGES: { value: string; label: string }[] = [
  { value: "en", label: "English" },
  { value: "hi", label: "हिन्दी Hindi" },
  { value: "te", label: "తెలుగు Telugu" },
  { value: "ta", label: "தமிழ் Tamil" },
  { value: "kn", label: "ಕನ್ನಡ Kannada" },
  { value: "mr", label: "मराठी Marathi" },
  { value: "bn", label: "বাংলা Bengali" },
  { value: "es", label: "Español Spanish" },
];
export const languageLabel = (v: string) => HELP_LANGUAGES.find((l) => l.value === v)?.label ?? v;

export interface HelpContent {
  title: string;
  summary: string;
  body: string;
  topic: string;
  popular: number;
  related: string[];
}

export interface HelpArticle {
  id: string;
  slug: string;
  country: string;
  language: string;
  status: "draft" | "published";
  version: number;
  live: HelpContent;
  draft: HelpContent | null;
  helpful_yes: number;
  helpful_no: number;
  published_at: string | null;
  updated_at: string;
  updated_by_name: string | null;
  can_edit: boolean;
}

export interface HelpHistoryEntry {
  version: number;
  action: "created" | "edited" | "published" | "unpublished";
  status: string;
  at: string;
  by_name: string | null;
  content: HelpContent;
}

export interface HelpFilters {
  country?: string;
  language?: string;
  topic?: string;
  status?: string;
  q?: string;
}

export function useHelpArticles(f: HelpFilters) {
  const params = Object.fromEntries(Object.entries(f).filter(([, v]) => v));
  return useQuery({
    queryKey: ["help", "articles", params],
    queryFn: async () => (await adminApi.get<HelpArticle[]>("/user/ops/help/articles", { params })).data,
  });
}

export function useHelpArticle(id: string | null) {
  return useQuery({
    queryKey: ["help", "article", id],
    queryFn: async () => (await adminApi.get<HelpArticle>(`/user/ops/help/articles/${id}`)).data,
    enabled: Boolean(id),
  });
}

export function useHelpHistory(id: string | null) {
  return useQuery({
    queryKey: ["help", "history", id],
    queryFn: async () => (await adminApi.get<HelpHistoryEntry[]>(`/user/ops/help/articles/${id}/history`)).data,
    enabled: Boolean(id),
  });
}

/** "Published", "Draft", or "Published · unpublished changes". */
export function statusWords(a: Pick<HelpArticle, "status" | "draft">): { text: string; tone: "live" | "draft" | "changes" } {
  if (a.status === "draft") return { text: "Draft", tone: "draft" };
  return a.draft ? { text: "Published · changes not live", tone: "changes" } : { text: "Published", tone: "live" };
}

export const countryLabel = (code: string, names: Record<string, string>) => (code === "*" ? "Every country" : names[code] ?? code);
