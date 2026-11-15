// Next 16 proxy (was middleware): passes the page's path to server components, so a
// first-time visitor on /{country}/... gets that country in the header (country,
// currency and languages) before anything else is known about them.
import { NextResponse, type NextRequest } from "next/server";

export function proxy(request: NextRequest) {
  const headers = new Headers(request.headers);
  headers.set("x-bg-path", request.nextUrl.pathname);
  return NextResponse.next({ request: { headers } });
}

export const config = {
  // pages only: not Next's assets, the food photos, icons or the sitemap/robots files
  matcher: ["/((?!_next/|food/|favicon|icon|apple-icon|robots.txt|sitemap.xml).*)"],
};
