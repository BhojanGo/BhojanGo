// node --test: JSON-LD can't end its <script> tag (R21 security review, S1).
import assert from "node:assert/strict";
import test from "node:test";

import { jsonLdHtml } from "../src/lib/jsonLd.ts";

test("a dish description can't close the JSON-LD script tag", () => {
  const evil = { "@type": "MenuItem", name: "Dal", description: "</script><script>alert(document.cookie)</script>" };
  const html = jsonLdHtml(evil);
  assert.ok(!html.includes("<"), html);
  assert.ok(!html.includes(">"), html);
  assert.ok(!/<\/script/i.test(html), html);
  // Still the same JSON for search engines.
  assert.deepEqual(JSON.parse(html), evil);
});

test("ampersands and line separators are escaped too, and the data survives", () => {
  const data = { name: "Rice & Curry " + String.fromCharCode(0x2028) + " <b>", n: 2 };
  const html = jsonLdHtml(data);
  assert.ok(!html.includes("&") && !html.includes(String.fromCharCode(0x2028)), html);
  assert.deepEqual(JSON.parse(html), data);
});

test("no page puts raw JSON.stringify output into dangerouslySetInnerHTML", async () => {
  const { readdir, readFile } = await import("node:fs/promises");
  const { join } = await import("node:path");
  const root = join(import.meta.dirname, "..", "src");
  const files = (await readdir(root, { recursive: true })).filter((f) => /\.(tsx|ts|jsx|js)$/.test(String(f)));
  const bad: string[] = [];
  for (const f of files) {
    const text = await readFile(join(root, String(f)), "utf8");
    if (/__html:\s*JSON\.stringify/.test(text)) bad.push(String(f));
  }
  assert.deepEqual(bad, [], "use jsonLdHtml from src/lib/jsonLd.ts");
});
