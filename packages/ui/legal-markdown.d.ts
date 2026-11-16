export type Inline =
  | { t: "text"; v: string }
  | { t: "code"; v: string }
  | { t: "strong"; children: Inline[] }
  | { t: "em"; children: Inline[] }
  | { t: "link"; href: string; children: Inline[] };

export type Block =
  | { type: "heading"; level: 2 | 3; id: string; text: string; inline: Inline[] }
  | { type: "p"; inline: Inline[] }
  | { type: "ul" | "ol"; items: Inline[][] }
  | { type: "hr" }
  | { type: "table"; head: Inline[][]; rows: Inline[][][] };

export declare function parse(markdown: string | null | undefined): Block[];
export declare function toc(blocks: Block[]): { id: string; text: string }[];
export declare function inline(src: string): Inline[];
export declare function slug(text: string): string;
export declare function plain(tokens: Inline[]): string;
export declare function safeHref(href: string): string | null;
