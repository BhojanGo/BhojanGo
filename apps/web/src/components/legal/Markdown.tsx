// Renders the tree from @bhojango/ui/markdown (admin-written Terms and Privacy)
// as React: no HTML strings, so nothing in a document can inject markup.
import type { Block, Inline } from "@bhojango/ui/markdown";
import Link from "next/link";
import type { ReactNode } from "react";

// "[To be appointed]", "[City — to be confirmed]": details the lawyer or the company must fill in, marked so nobody misses them.
const PLACEHOLDER = /(\[[^\]]*(?:to be (?:appointed|confirmed|decided)|To be appointed)[^\]]*\])/;

function Text({ v }: { v: string }): ReactNode {
  const parts = v.split(PLACEHOLDER);
  if (parts.length === 1) return v;
  return parts.map((p, i) => (i % 2 ? <mark key={i} className="rounded bg-[#FBF4E6] px-1 text-kohl ring-1 ring-kesar print:ring-0">{p}</mark> : p));
}

function Inlines({ tokens }: { tokens: Inline[] }): ReactNode {
  return tokens.map((t, i) => {
    switch (t.t) {
      case "text": return <Text key={i} v={t.v} />;
      case "code": return <code key={i} className="rounded bg-porcelain px-1 font-mono">{t.v}</code>;
      case "strong": return <strong key={i} className="font-semibold text-kohl"><Inlines tokens={t.children} /></strong>;
      case "em": return <em key={i}><Inlines tokens={t.children} /></em>;
      case "link":
        return t.href.startsWith("/")
          ? <Link key={i} href={t.href} className="font-semibold text-peacock underline underline-offset-2 hover:text-peacock-deep"><Inlines tokens={t.children} /></Link>
          : <a key={i} href={t.href} className="font-semibold text-peacock underline underline-offset-2 hover:text-peacock-deep [overflow-wrap:anywhere]"
              {...(t.href.startsWith("http") ? { rel: "noopener noreferrer" } : {})}><Inlines tokens={t.children} /></a>;
    }
  });
}

export function Markdown({ blocks }: { blocks: Block[] }) {
  return (
    <div className="legal-body text-body-lg leading-[1.7] text-[#24383B]">
      {blocks.map((b, i) => {
        switch (b.type) {
          case "heading":
            return b.level === 2
              ? <h2 key={i} id={b.id} className="mt-12 scroll-mt-24 border-t border-line pt-8 text-h2 text-kohl first:mt-0 first:border-0 first:pt-0 print:mt-8 print:pt-4"><Inlines tokens={b.inline} /></h2>
              : <h3 key={i} id={b.id} className="mt-8 scroll-mt-24 text-h3 text-kohl"><Inlines tokens={b.inline} /></h3>;
          case "p": return <p key={i} className="mt-4"><Inlines tokens={b.inline} /></p>;
          case "ul":
            return <ul key={i} className="mt-4 list-disc space-y-2 pl-6 marker:text-peacock">{b.items.map((it, j) => <li key={j} className="pl-1"><Inlines tokens={it} /></li>)}</ul>;
          case "ol":
            return <ol key={i} className="mt-4 list-decimal space-y-2 pl-6 marker:font-semibold marker:text-peacock">{b.items.map((it, j) => <li key={j} className="pl-1"><Inlines tokens={it} /></li>)}</ol>;
          case "hr": return <hr key={i} className="my-8 border-line" />;
          case "table":
            return (
              <div key={i} className="mt-5 overflow-hidden rounded-card border border-line">
                <table className="w-full border-collapse text-left text-body">
                  <thead className="bg-porcelain">
                    <tr>{b.head.map((c, j) => <th key={j} scope="col" className="px-3 py-2.5 align-top text-label font-bold text-kohl md:px-4"><Inlines tokens={c} /></th>)}</tr>
                  </thead>
                  <tbody>
                    {b.rows.map((row, r) => (
                      <tr key={r} className="border-t border-line">
                        {row.map((c, j) => <td key={j} className="px-3 py-2.5 align-top [overflow-wrap:anywhere] md:px-4"><Inlines tokens={c} /></td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
        }
      })}
    </div>
  );
}
