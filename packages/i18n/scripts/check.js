// Lint for messages: valid JSON, no empty strings, and the same {placeholders}
// in every language as in English (a translation that drops {price} would show
// the wrong thing).
const fs = require("node:fs");
const path = require("node:path");

const dir = path.join(__dirname, "..", "messages");
const flat = (o, p = "") => Object.entries(o).flatMap(([k, v]) =>
  v && typeof v === "object" ? flat(v, `${p}${k}.`) : [[`${p}${k}`, v]]);
const en = new Map(flat(JSON.parse(fs.readFileSync(path.join(dir, "en.json"), "utf8"))));
const vars = (s) => [...String(s).matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");
let problems = 0;
for (const file of fs.readdirSync(dir).filter((f) => f.endsWith(".json"))) {
  const msgs = flat(JSON.parse(fs.readFileSync(path.join(dir, file), "utf8")));
  for (const [key, value] of msgs) {
    if (typeof value !== "string" || !value.trim()) {
      console.error(`${file}: ${key} is empty`);
      problems++;
    } else if (en.has(key) && vars(en.get(key)) !== vars(value)) {
      console.error(`${file}: ${key} has {${vars(value)}}, English has {${vars(en.get(key))}}`);
      problems++;
    }
  }
}
if (problems) process.exit(1);
console.log(`messages ok (${fs.readdirSync(dir).filter((f) => f.endsWith(".json")).length} languages, ${en.size} keys)`);
