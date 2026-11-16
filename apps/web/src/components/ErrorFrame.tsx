// The frame of the not-found and error pages (R8): the title, what to do, the
// ways on, and a food photo beside them on wide screens. No hooks: used by the
// server's not-found page and the client error boundary alike.
import Link from "next/link";
import type { ReactNode } from "react";

/** The shared frame of the not-found and error pages: text and actions, a food photo beside them on wide screens. */
export function ErrorFrame({ photo, title, body, children }: { photo: string | null; title: string; body: string; children: ReactNode }) {
  return (
    <div className="mx-auto grid max-w-[1200px] items-center gap-8 px-4 pb-16 pt-10 md:px-8 md:pt-16 lg:grid-cols-[minmax(0,1fr)_420px] lg:gap-16 lg:px-12 lg:pb-24">
      <div className="min-w-0 max-w-[560px]">
        <h1 className="m-0 text-h1 tracking-[-0.8px]">{title}</h1>
        <p className="mt-3 text-body-lg text-[#3D4A4E]">{body}</p>
        <div className="mt-8 flex flex-col gap-6">{children}</div>
      </div>
      {photo && (
        <div className="hidden overflow-hidden rounded-[28px] bg-[#DDEBEC] lg:block" aria-hidden="true">
          {/* eslint-disable-next-line @next/next/no-img-element -- a local WebP from the photo library */}
          <img src={photo} alt="" className="block aspect-[4/5] w-full object-cover" />
        </div>
      )}
    </div>
  );
}

export function WayList({ label, ways }: { label: string; ways: { href: string; label: string }[] }) {
  return (
    <nav aria-label={label}>
      <ul className="m-0 flex list-none flex-col gap-2 p-0 sm:flex-row sm:flex-wrap">
        {ways.map((w) => (
          <li key={w.href}>
            <Link
              href={w.href}
              className="flex min-h-12 items-center justify-between gap-3 rounded-full border border-[#E2E7E8] px-5 text-label text-[#111418] hover:border-[#0B5D66] hover:text-[#0B5D66]"
            >
              {w.label}
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
