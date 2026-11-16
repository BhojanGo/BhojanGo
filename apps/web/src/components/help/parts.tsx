// Help centre pieces that render on the server: topic icons, breadcrumbs,
// article lists and the article body (round 8, F9).
import { parseMarkdown, type MdBlock, type MdInline } from "@bhojango/ui/markdown";
import Link from "next/link";
import type { ReactNode } from "react";

import { ChevronRight } from "@/components/Icons";
import { articleHref, type HelpCard, type HelpTopic } from "@/lib/help";

const PATHS: Record<HelpTopic, ReactNode> = {
  orders: (
    <>
      <path d="M6 8h12l-1 12H7L6 8z" />
      <path d="M9 8V6a3 3 0 0 1 6 0v2" />
    </>
  ),
  "payments-refunds": (
    <>
      <rect x="3" y="6" width="18" height="13" rx="2" />
      <path d="M3 10h18M7 15h4" />
    </>
  ),
  delivery: (
    <>
      <circle cx="6.5" cy="17" r="2.5" />
      <circle cx="17.5" cy="17" r="2.5" />
      <path d="M9 17h6l-2-6h-3M15 11h3l2 3M4 11h5" />
    </>
  ),
  account: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6" />
    </>
  ),
  "kitchen-partners": (
    <>
      <path d="M7 14a4 4 0 1 1 2.5-7.1A4.5 4.5 0 0 1 17 8a3.5 3.5 0 0 1 0 7H7z" />
      <path d="M8 15v5h9v-5" />
    </>
  ),
  "delivery-partners": (
    <>
      <rect x="4" y="9" width="11" height="9" rx="1.5" />
      <path d="M15 12h3l2 3v3h-5M8 9V6h4v3" />
      <circle cx="8" cy="19" r="1.5" />
      <circle cx="17" cy="19" r="1.5" />
    </>
  ),
};

export function TopicIcon({ topic, size = 24 }: { topic: HelpTopic; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {PATHS[topic]}
    </svg>
  );
}

export function Breadcrumbs({ label, items }: { label: string; items: { href?: string; text: string }[] }) {
  return (
    <nav aria-label={label} className="text-small text-muted">
      <ol className="flex flex-wrap items-center gap-x-1.5 gap-y-1">
        {items.map((it, i) => (
          <li key={i} className="flex min-w-0 items-center gap-1.5">
            {i > 0 ? <ChevronRight size={12} aria-hidden="true" /> : null}
            {it.href ? (
              <Link href={it.href} className="rounded font-semibold text-peacock hover:underline">{it.text}</Link>
            ) : (
              <span aria-current="page" className="truncate">{it.text}</span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}

/** A list of articles as rows: title, summary, chevron. */
export function ArticleList({ items, dense }: { items: HelpCard[]; dense?: boolean }) {
  return (
    <ul className="divide-y divide-line overflow-hidden rounded-card border border-line bg-white">
      {items.map((a) => (
        <li key={a.slug}>
          <Link href={articleHref(a)}
            className="group flex min-h-[56px] items-center gap-4 px-4 py-3.5 hover:bg-porcelain focus-visible:bg-porcelain sm:px-5">
            <span className="min-w-0 flex-grow">
              <span className="block text-label font-semibold text-kohl group-hover:text-peacock-deep">{a.title}</span>
              {!dense && a.summary ? <span className="mt-0.5 block text-small text-muted">{a.summary}</span> : null}
            </span>
            <ChevronRight className="shrink-0 text-muted" />
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** Articles as cards in a grid (popular articles). */
export function ArticleGrid({ items }: { items: HelpCard[] }) {
  return (
    <ul className="grid gap-3 md:grid-cols-2">
      {items.map((a) => (
        <li key={a.slug}>
          <Link href={articleHref(a)}
            className="group flex h-full items-center gap-4 rounded-card border border-line bg-white px-5 py-4 hover:border-peacock focus-visible:border-peacock">
            <span className="min-w-0 flex-grow">
              <span className="block text-label font-bold text-kohl group-hover:text-peacock-deep">{a.title}</span>
              <span className="mt-1 line-clamp-2 block text-small text-muted">{a.summary}</span>
            </span>
            <ChevronRight className="shrink-0 text-muted" />
          </Link>
        </li>
      ))}
    </ul>
  );
}

function Inline({ nodes }: { nodes: MdInline[] }) {
  return (
    <>
      {nodes.map((n, i) => {
        switch (n.type) {
          case "text":
            return <span key={i}>{n.text}</span>;
          case "code":
            return <code key={i} className="rounded bg-porcelain px-1 py-0.5">{n.text}</code>;
          case "strong":
            return <strong key={i} className="font-bold text-kohl"><Inline nodes={n.children} /></strong>;
          case "em":
            return <em key={i}><Inline nodes={n.children} /></em>;
          case "link":
            return n.href.startsWith("/") ? (
              <Link key={i} href={n.href} className="font-semibold text-peacock underline decoration-peacock/40 underline-offset-2 hover:decoration-peacock">
                <Inline nodes={n.children} />
              </Link>
            ) : (
              <a key={i} href={n.href} rel="noopener noreferrer" className="font-semibold text-peacock underline underline-offset-2">
                <Inline nodes={n.children} />
              </a>
            );
        }
      })}
    </>
  );
}

function Block({ b }: { b: MdBlock }) {
  switch (b.type) {
    case "h2":
      return <h2 className="pt-3 text-h3 text-kohl"><Inline nodes={b.inline} /></h2>;
    case "h3":
      return <h3 className="pt-1 text-body-lg font-bold text-kohl"><Inline nodes={b.inline} /></h3>;
    case "quote":
      return (
        <p className="rounded-xl border-l-4 border-peacock bg-peacock-mist px-4 py-3 text-kohl">
          <Inline nodes={b.inline} />
        </p>
      );
    case "ul":
      return <ul className="list-disc space-y-1.5 pl-6 marker:text-peacock">{b.items.map((it, i) => <li key={i}><Inline nodes={it} /></li>)}</ul>;
    case "ol":
      return <ol className="list-decimal space-y-1.5 pl-6 marker:font-bold marker:text-peacock">{b.items.map((it, i) => <li key={i}><Inline nodes={it} /></li>)}</ol>;
    default:
      return <p><Inline nodes={b.inline} /></p>;
  }
}

/** An article body (the Help centre's Markdown: text only, never HTML). */
export function ArticleBody({ markdown }: { markdown: string }) {
  return (
    <div className="space-y-4 text-body leading-relaxed text-[#26363A]">
      {parseMarkdown(markdown).map((b, i) => <Block key={i} b={b} />)}
    </div>
  );
}
