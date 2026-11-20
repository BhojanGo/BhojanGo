// JSON-LD for a <script type="application/ld+json"> tag (R21 security review, S1).
// JSON.stringify leaves "<" alone, so a kitchen name or dish description holding
// "</script><script>..." would close the tag and run as a script on our page.
// Escaping <, > and & (and the two line separators JavaScript treats as line ends)
// keeps the same JSON for search engines and can never end the tag.
const LS = new RegExp(String.fromCharCode(0x2028), "g");
const PS = new RegExp(String.fromCharCode(0x2029), "g");

export function jsonLdHtml(data: unknown): string {
  return JSON.stringify(data)
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e")
    .replace(/&/g, "\\u0026")
    .replace(LS, "\\u2028")
    .replace(PS, "\\u2029");
}
