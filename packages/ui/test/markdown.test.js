// node --test: the Help centre's Markdown (round 8, F9).
const test = require("node:test");
const assert = require("node:assert/strict");
const { parseMarkdown, plainText, safeHref } = require("../markdown");

test("blocks: headings, paragraphs, lists, notes", () => {
  const b = parseMarkdown("# Top\n\nOne line\nsame paragraph\n\n## Steps\n1. First\n2. Second\n\n- a\n- b\n\n> Careful\n### Small");
  assert.deepEqual(b.map((x) => x.type), ["h2", "p", "h2", "ol", "ul", "quote", "h3"]);
  assert.equal(plainText(b[1].inline), "One line same paragraph");
  assert.equal(b[3].items.length, 2);
});

test("inline: bold, italic, code, links", () => {
  const [p] = parseMarkdown("Tap **Report a problem** on *your* order, see [the PIN](/help/a/delivery-pin) and `UPI`.");
  assert.deepEqual(p.inline.map((n) => n.type), ["text", "strong", "text", "em", "text", "link", "text", "code", "text"]);
  assert.equal(p.inline[5].href, "/help/a/delivery-pin");
});

test("no HTML and no unsafe links", () => {
  const [p] = parseMarkdown('<script>alert(1)</script> [x](javascript:alert(1)) [y](//evil.example) [z](https://ok.example)');
  assert.equal(p.inline[0].type, "text");
  assert.ok(p.inline[0].text.includes("<script>"));
  assert.ok(!p.inline.some((n) => n.type === "link" && !n.href.startsWith("https://")));
  assert.equal(safeHref("javascript:alert(1)"), null);
  assert.equal(safeHref("mailto:help@example.com"), "mailto:help@example.com");
});

test("bold with an italic inside, and empty input", () => {
  const [p] = parseMarkdown("**KITCHEN** and **DELIVERY PARTNER**");
  assert.equal(p.inline.filter((n) => n.type === "strong").length, 2);
  assert.deepEqual(parseMarkdown(""), []);
});
