// The console's own "not found" (R8): any unknown URL in admin. Plain words and
// the way back to the overview (or sign-in, which sends you on to it).
import type { Metadata } from "next";

import { ConsoleMessage } from "@/components/console/ConsoleMessage";

export const metadata: Metadata = { title: "Page not found · BhojanGo Admin" };

export default function NotFound() {
  return <ConsoleMessage title="This page isn't in the console" body="The link may be old, or the page has moved. The overview has everything you can see." />;
}
