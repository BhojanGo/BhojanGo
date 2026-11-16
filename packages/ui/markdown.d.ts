export type MdInline =
  | { type: "text"; text: string }
  | { type: "code"; text: string }
  | { type: "strong"; children: MdInline[] }
  | { type: "em"; children: MdInline[] }
  | { type: "link"; href: string; children: MdInline[] };

export type MdBlock =
  | { type: "h2" | "h3" | "p" | "quote"; inline: MdInline[] }
  | { type: "ul" | "ol"; items: MdInline[][] };

export function parseMarkdown(src: string): MdBlock[];
export function plainText(nodes: MdInline[]): string;
export function safeHref(href: string): string | null;
