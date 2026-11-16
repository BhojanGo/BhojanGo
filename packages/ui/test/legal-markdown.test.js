// node --test: the Markdown reader for Terms, Privacy and Help documents.
const test = require("node:test");
const assert = require("node:assert/strict");
const { parse, toc, inline, slug, safeHref } = require("../legal-markdown");

test("headings get stable ids and make the table of contents", () => {
  const blocks = parse("## 1. About these terms\n\nText.\n\n### Who can have an account\n\n## 2. About these terms\n\n# Top");
  assert.deepEqual(toc(blocks), [
    { id: "about-these-terms", text: "1. About these terms" },
    { id: "about-these-terms-2", text: "2. About these terms" },
    { id: "top", text: "Top" },
  ]);
  assert.equal(blocks[2].level, 3);
  assert.equal(slug("गोपनीयता सूचना"), "गोपनीयता-सूचना");
  assert.equal(slug("1."), "section");
});

test("paragraphs join lines; lists, tables and rules", () => {
  const blocks = parse("One line\nsame paragraph.\n\n- a **bold** item\n- second\n\n1. first\n2. second\n\n| Name | Why |\n|---|---|\n| bg_lang | Your language |\n\n---");
  assert.deepEqual(blocks.map((b) => b.type), ["p", "ul", "ol", "table", "hr"]);
  assert.equal(blocks[0].inline[0].v, "One line same paragraph.");
  assert.equal(blocks[1].items.length, 2);
  assert.deepEqual(blocks[1].items[0][1], { t: "strong", children: [{ t: "text", v: "bold" }] });
  assert.equal(blocks[3].rows[0][0][0].v, "bg_lang");
});

test("links are kept only when safe; emails become mailto links", () => {
  assert.deepEqual(inline("[Privacy](/privacy)"), [{ t: "link", href: "/privacy", children: [{ t: "text", v: "Privacy" }] }]);
  assert.deepEqual(inline("[x](javascript:alert(1))"), [{ t: "text", v: "x" }, { t: "text", v: ")" }]);
  assert.equal(safeHref("//evil.example"), null);
  assert.equal(safeHref("https://example.com"), "https://example.com");
  const e = inline("Write to privacy@bhojango.com today");
  assert.deepEqual(e[1], { t: "link", href: "mailto:privacy@bhojango.com", children: [{ t: "text", v: "privacy@bhojango.com" }] });
});

test("markup in a document stays text", () => {
  const blocks = parse("<script>alert(1)</script>");
  assert.deepEqual(blocks, [{ type: "p", inline: [{ t: "text", v: "<script>alert(1)</script>" }] }]);
});
