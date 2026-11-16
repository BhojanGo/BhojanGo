// The small Markdown the Help centre's articles are written in (round 8, F9),
// parsed to a tree the website and the admin preview render as React elements.
// Never HTML: whatever an editor types is text, so an article can't inject a
// script. Links go to our own pages (/...), https:// or mailto: only.
//
// Blocks: "## " and "### " headings ("# " counts as "## ": the page has the h1),
// paragraphs, "- " / "* " bullets, "1. " numbered lists, "> " notes.
// Inline: **bold**, *italic* or _italic_, `code`, [text](link).

function safeHref(href) {
  const h = String(href || "").trim();
  if (/^\/(?!\/)/.test(h) || /^https:\/\//i.test(h) || /^mailto:/i.test(h) || /^#[\w-]+$/.test(h)) return h;
  return null;
}

function inline(src) {
  const out = [];
  let text = "";
  const flush = () => {
    if (text) out.push({ type: "text", text });
    text = "";
  };
  let i = 0;
  while (i < src.length) {
    const rest = src.slice(i);
    let m;
    if ((m = /^\*\*([^*]+(?:\*(?!\*)[^*]*)*)\*\*/.exec(rest))) {
      flush();
      out.push({ type: "strong", children: inline(m[1]) });
      i += m[0].length;
    } else if ((m = /^\*([^*\s][^*]*?)\*/.exec(rest)) || (m = /^_([^_\s][^_]*?)_(?![\w])/.exec(rest))) {
      flush();
      out.push({ type: "em", children: inline(m[1]) });
      i += m[0].length;
    } else if ((m = /^`([^`]+)`/.exec(rest))) {
      flush();
      out.push({ type: "code", text: m[1] });
      i += m[0].length;
    } else if ((m = /^\[([^\]]+)\]\(([^)\s]+)\)/.exec(rest))) {
      flush();
      const href = safeHref(m[2]);
      if (href) out.push({ type: "link", href, children: inline(m[1]) });
      else out.push(...inline(m[1]));
      i += m[0].length;
    } else {
      text += src[i];
      i += 1;
    }
  }
  flush();
  return out;
}

/** Markdown → blocks. */
function parseMarkdown(src) {
  const lines = String(src || "").replace(/\r\n?/g, "\n").split("\n");
  const blocks = [];
  let para = [];
  let list = null;
  let quote = [];
  const endPara = () => {
    if (para.length) blocks.push({ type: "p", inline: inline(para.join(" ")) });
    para = [];
  };
  const endList = () => {
    if (list) blocks.push(list);
    list = null;
  };
  const endQuote = () => {
    if (quote.length) blocks.push({ type: "quote", inline: inline(quote.join(" ")) });
    quote = [];
  };
  const endAll = () => {
    endPara();
    endList();
    endQuote();
  };
  for (const raw of lines) {
    const line = raw.trim();
    let m;
    if (!line) {
      endAll();
    } else if ((m = /^(#{1,3})\s+(.*)$/.exec(line))) {
      endAll();
      blocks.push({ type: m[1].length === 3 ? "h3" : "h2", inline: inline(m[2]) });
    } else if ((m = /^[-*]\s+(.*)$/.exec(line))) {
      endPara();
      endQuote();
      if (!list || list.type !== "ul") {
        endList();
        list = { type: "ul", items: [] };
      }
      list.items.push(inline(m[1]));
    } else if ((m = /^\d+[.)]\s+(.*)$/.exec(line))) {
      endPara();
      endQuote();
      if (!list || list.type !== "ol") {
        endList();
        list = { type: "ol", items: [] };
      }
      list.items.push(inline(m[1]));
    } else if ((m = /^>\s?(.*)$/.exec(line))) {
      endPara();
      endList();
      quote.push(m[1]);
    } else if (list && /^\s{2,}/.test(raw)) {
      // an indented line continues the last list item
      const last = list.items[list.items.length - 1];
      last.push({ type: "text", text: " " }, ...inline(line));
    } else {
      endList();
      endQuote();
      para.push(line);
    }
  }
  endAll();
  return blocks;
}

/** Plain text of inline nodes (headings' anchors, previews). */
function plainText(nodes) {
  return nodes.map((n) => (n.type === "text" || n.type === "code" ? n.text : plainText(n.children))).join("");
}

module.exports = { parseMarkdown, plainText, safeHref };
