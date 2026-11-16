/**
 * The Help article preview: the same Markdown parser as the website
 * (@bhojango/ui/markdown) and the same look, so what you see is what
 * customers get. Text only: whatever is typed is never HTML.
 */
import { parseMarkdown, type MdBlock, type MdInline } from "@bhojango/ui/markdown";

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
            return (
              <a key={i} href={n.href} target="_blank" rel="noopener noreferrer" title={n.href}
                className="font-semibold text-peacock underline underline-offset-2"><Inline nodes={n.children} /></a>
            );
        }
      })}
    </>
  );
}

function Block({ b }: { b: MdBlock }) {
  switch (b.type) {
    case "h2":
      return <h2 className="m-0 pt-3 text-h3 text-kohl"><Inline nodes={b.inline} /></h2>;
    case "h3":
      return <h3 className="m-0 pt-1 text-body font-bold text-kohl"><Inline nodes={b.inline} /></h3>;
    case "quote":
      return <p className="m-0 rounded-xl border-l-4 border-peacock bg-peacock-wash px-4 py-3 text-kohl"><Inline nodes={b.inline} /></p>;
    case "ul":
      return <ul className="m-0 list-disc space-y-1.5 pl-6">{b.items.map((it, i) => <li key={i}><Inline nodes={it} /></li>)}</ul>;
    case "ol":
      return <ol className="m-0 list-decimal space-y-1.5 pl-6">{b.items.map((it, i) => <li key={i}><Inline nodes={it} /></li>)}</ol>;
    default:
      return <p className="m-0"><Inline nodes={b.inline} /></p>;
  }
}

export function MarkdownPreview({ title, summary, body }: { title: string; summary: string; body: string }) {
  const blocks = parseMarkdown(body);
  return (
    <article className="space-y-4 leading-relaxed text-[#26363A]" aria-label="Preview">
      <header className="space-y-2 border-b border-line pb-4">
        <h1 className="m-0 text-h1 text-kohl">{title || <span className="text-muted">Title</span>}</h1>
        {summary ? <p className="m-0 text-body text-muted">{summary}</p> : null}
      </header>
      {blocks.length ? blocks.map((b, i) => <Block key={i} b={b} />) : <p className="m-0 text-muted">Nothing written yet.</p>}
    </article>
  );
}
