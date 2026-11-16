// A small Markdown reader for admin-written documents (Terms, Privacy, Help):
// headings (## and ###), paragraphs, bullet and numbered lists, pipe tables,
// horizontal rules, **bold**, *italic*, `code`, [links](/path) and bare emails.
// It returns a tree (no HTML strings), so web and admin render it with React and
// nothing in a document can inject markup. Links are kept only for http(s),
// mailto and site-relative targets. Shared by web and admin; no DOM, no React.

/** "1. About these terms" → "about-these-terms" (leading numbers dropped). */
function slug(text) {
  const s = String(text)
    .toLowerCase()
    .replace(/^[\d.\s]+/, "")
    .replace(/[^\p{L}\p{M}\p{N}]+/gu, "-")
    .replace(/^-+|-+$/g, "");
  return s || "section";
}

function safeHref(href) {
  const h = String(href).trim();
  if (/^(https?:\/\/|mailto:)/i.test(h)) return h;
  if (/^\/(?!\/)/.test(h) || h.startsWith("#")) return h;
  return null;
}

const EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;

/** Plain text with bare email addresses turned into mailto links. */
function textWithEmails(text, out) {
  let last = 0;
  for (const m of text.matchAll(EMAIL)) {
    if (m.index > last) out.push({ t: "text", v: text.slice(last, m.index) });
    out.push({ t: "link", href: `mailto:${m[0]}`, children: [{ t: "text", v: m[0] }] });
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push({ t: "text", v: text.slice(last) });
}

/** Inline Markdown → [{t: text|strong|em|code|link, ...}]. */
function inline(src) {
  const out = [];
  const re = /\*\*(.+?)\*\*|\*(?!\s)(.+?)\*|`([^`]+)`|\[([^\]]+)\]\(([^)\s]+)\)/g;
  let last = 0;
  for (const m of src.matchAll(re)) {
    if (m.index > last) textWithEmails(src.slice(last, m.index), out);
    if (m[1] !== undefined) out.push({ t: "strong", children: inline(m[1]) });
    else if (m[2] !== undefined) out.push({ t: "em", children: inline(m[2]) });
    else if (m[3] !== undefined) out.push({ t: "code", v: m[3] });
    else {
      const href = safeHref(m[5]);
      const children = inline(m[4]);
      if (href) out.push({ t: "link", href, children });
      else out.push(...children);
    }
    last = m.index + m[0].length;
  }
  if (last < src.length) textWithEmails(src.slice(last), out);
  return out;
}

/** The plain text of inline tokens (headings' ids, the table of contents). */
function plain(tokens) {
  return tokens.map((t) => (t.children ? plain(t.children) : t.v ?? "")).join("");
}

const cells = (line) => line.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());

/**
 * Markdown → blocks:
 *   {type: "heading", level: 2|3, id, text, inline}
 *   {type: "p", inline} · {type: "ul"|"ol", items: inline[]} · {type: "hr"}
 *   {type: "table", head: inline[], rows: inline[][]}
 */
function parse(markdown) {
  const lines = String(markdown ?? "").replace(/\r\n?/g, "\n").split("\n");
  const blocks = [];
  const ids = new Map();
  let para = [];
  const flush = () => {
    if (para.length) blocks.push({ type: "p", inline: inline(para.join(" ")) });
    para = [];
  };
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const t = line.trim();
    if (!t) { flush(); continue; }
    const h = /^(#{1,4})\s+(.*)$/.exec(t);
    if (h) {
      flush();
      const level = Math.min(Math.max(h[1].length, 2), 3);
      const toks = inline(h[2].trim());
      const text = plain(toks);
      const base = slug(text);
      const n = (ids.get(base) ?? 0) + 1;
      ids.set(base, n);
      blocks.push({ type: "heading", level, id: n > 1 ? `${base}-${n}` : base, text, inline: toks });
      continue;
    }
    if (/^(-{3,}|\*{3,})$/.test(t)) { flush(); blocks.push({ type: "hr" }); continue; }
    if (t.startsWith("|") && i + 1 < lines.length && /^\|?\s*:?-{2,}/.test(lines[i + 1].trim())) {
      flush();
      const head = cells(t).map(inline);
      const rows = [];
      i += 2;
      while (i < lines.length && lines[i].trim().startsWith("|")) rows.push(cells(lines[i++]).map(inline));
      i--;
      blocks.push({ type: "table", head, rows });
      continue;
    }
    const bullet = /^[-*]\s+(.*)$/.exec(t);
    const numbered = /^\d+[.)]\s+(.*)$/.exec(t);
    if (bullet || numbered) {
      flush();
      const type = bullet ? "ul" : "ol";
      const items = [];
      let cur = (bullet ?? numbered)[1];
      for (i++; i < lines.length; i++) {
        const nt = lines[i].trim();
        const nb = type === "ul" ? /^[-*]\s+(.*)$/.exec(nt) : /^\d+[.)]\s+(.*)$/.exec(nt);
        if (nb) { items.push(inline(cur)); cur = nb[1]; continue; }
        if (nt && /^\s{2,}/.test(lines[i])) { cur += ` ${nt}`; continue; } // an indented continuation
        break;
      }
      items.push(inline(cur));
      i--;
      blocks.push({ type, items });
      continue;
    }
    para.push(t);
  }
  flush();
  return blocks;
}

/** The ## headings, for a table of contents: [{id, text}]. */
function toc(blocks) {
  return blocks.filter((b) => b.type === "heading" && b.level === 2).map((b) => ({ id: b.id, text: b.text }));
}

module.exports = { parse, toc, inline, slug, plain, safeHref };
