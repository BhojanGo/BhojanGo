// The admin's preview of a document's Markdown, read with the same parser the
// website uses (@bhojango/ui/legal-markdown), so what you see is what gets published.
import { parse, type Inline } from "@bhojango/ui/legal-markdown";
import type { ReactNode } from "react";

function Inlines({ tokens }: { tokens: Inline[] }): ReactNode {
  return tokens.map((t, i) => {
    switch (t.t) {
      case "text": return t.v;
      case "code": return <code key={i} className="rounded bg-porcelain px-1">{t.v}</code>;
      case "strong": return <strong key={i}><Inlines tokens={t.children} /></strong>;
      case "em": return <em key={i}><Inlines tokens={t.children} /></em>;
      case "link": return <a key={i} href={t.href} target="_blank" rel="noopener noreferrer" className="font-semibold text-peacock underline"><Inlines tokens={t.children} /></a>;
    }
  });
}

export function LegalMarkdownPreview({ source }: { source: string }) {
  const blocks = parse(source);
  return (
    <div className="space-y-3 text-body leading-relaxed text-kohl" data-testid="legal-preview">
      {blocks.map((b, i) => {
        switch (b.type) {
          case "heading":
            return b.level === 2
              ? <h2 key={i} id={b.id} className="m-0 pt-4 text-h2"><Inlines tokens={b.inline} /></h2>
              : <h3 key={i} id={b.id} className="m-0 pt-2 text-h3"><Inlines tokens={b.inline} /></h3>;
          case "p": return <p key={i} className="m-0"><Inlines tokens={b.inline} /></p>;
          case "ul": return <ul key={i} className="m-0 list-disc space-y-1 pl-6">{b.items.map((it, j) => <li key={j}><Inlines tokens={it} /></li>)}</ul>;
          case "ol": return <ol key={i} className="m-0 list-decimal space-y-1 pl-6">{b.items.map((it, j) => <li key={j}><Inlines tokens={it} /></li>)}</ol>;
          case "hr": return <hr key={i} className="border-line" />;
          case "table":
            return (
              <table key={i} className="w-full border-collapse text-left text-small">
                <thead><tr>{b.head.map((c, j) => <th key={j} className="border border-line bg-porcelain px-2 py-1.5"><Inlines tokens={c} /></th>)}</tr></thead>
                <tbody>{b.rows.map((row, r) => <tr key={r}>{row.map((c, j) => <td key={j} className="border border-line px-2 py-1.5 align-top"><Inlines tokens={c} /></td>)}</tr>)}</tbody>
              </table>
            );
        }
      })}
    </div>
  );
}
