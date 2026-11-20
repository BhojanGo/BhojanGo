// Next 16 proxy (was middleware), for every page:
// - passes the page's path to server components, so a first-time visitor on /{country}/...
//   gets that country in the header (country, currency and languages) before anything else
//   is known about them;
// - R22 security review (S9): a fresh nonce for the page and the Content-Security-Policy that
//   only lets scripts carrying it run (no 'unsafe-inline'). Next reads the nonce from the
//   request's CSP header and puts it on its own scripts; the pages are rendered per request
//   (the root layout reads the request), so every page gets its own.
import { contentSecurityPolicy, newNonce } from "@bhojango/ui/security-headers";
import { NextResponse, type NextRequest } from "next/server";

import { WEB_CSP } from "@/lib/csp";

export function proxy(request: NextRequest) {
  const nonce = newNonce();
  const csp = contentSecurityPolicy(WEB_CSP, nonce);
  const headers = new Headers(request.headers);
  headers.set("x-bg-path", request.nextUrl.pathname);
  headers.set("x-nonce", nonce);
  headers.set("Content-Security-Policy", csp);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  // pages only: not Next's assets, the food photos, icons or the sitemap/robots files
  matcher: ["/((?!_next/|food/|favicon|icon|apple-icon|robots.txt|sitemap.xml).*)"],
};
