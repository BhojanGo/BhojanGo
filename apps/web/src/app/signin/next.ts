/** Only paths on this site ("/checkout"), never another site ("//evil", "https://...").
 * R21 security review: browsers drop tabs and newlines from URLs, so "/<tab>/evil.com"
 * became "//evil.com". Control characters and backslashes are refused, and the path is
 * resolved the way the browser will: it must stay on this site. */
const BACKSLASH = 92;

export function safeNext(next: string | null | undefined): string {
  if (!next || !next.startsWith("/")) return "/";
  if ([...next].some((ch) => ch.charCodeAt(0) < 32 || ch.charCodeAt(0) === 127 || ch.charCodeAt(0) === BACKSLASH)) return "/";
  try {
    const base = "https://here.invalid";
    const url = new URL(next, base);
    return url.origin === base && !url.pathname.startsWith("//") ? `${url.pathname}${url.search}${url.hash}` : "/";
  } catch {
    return "/";
  }
}
