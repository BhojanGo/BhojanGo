// The frame of the console's not-found and error pages (R8): the logo, what
// happened in plain words, and the way back to the overview. No hooks.
import Link from "next/link";
import type { ReactNode } from "react";

import { Logo } from "@bhojango/ui";

/** The frame of the console's not-found and error pages. */
export function ConsoleMessage({ title, body, children }: { title: string; body: string; children?: ReactNode }) {
  return (
    <main className="flex min-h-[calc(100vh-40px)] items-center justify-center bg-peacock-wash px-4 py-12 font-sans text-kohl">
      <div className="w-full max-w-md rounded-2xl border border-line bg-white p-8 shadow-sm">
        <Logo size={32} suffix="admin" />
        <h1 className="mt-6 text-h2">{title}</h1>
        <p className="mt-2 text-small text-muted">{body}</p>
        <div className="mt-6 flex flex-wrap gap-3">
          {children}
          <Link href="/overview" className="inline-flex min-h-11 items-center rounded-full bg-peacock px-5 text-label text-white hover:bg-peacock-dark hover:text-white">
            Go to the overview
          </Link>
        </div>
      </div>
    </main>
  );
}
