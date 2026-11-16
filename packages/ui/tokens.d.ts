export declare const color: {
  peacock: string; peacockDeep: string; peacockTint: string; peacockMist: string; kohl: string; kesar: string;
  kesarBright: string; porcelain: string; white: string; line: string; lineStrong: string; divider: string;
  muted: string; faint: string; chili: string; plate: string; mapGround: string;
};
export declare const dark: {
  ground: string; surface: string; raised: string; line: string; lineStrong: string; text: string; muted: string; link: string;
};
export declare const space: { 1: 4; 2: 8; 3: 12; 4: 16; 5: 20; 6: 24; 8: 32; 12: 48 };
export declare const radius: { chip: 8; card: 16; sheet: 24; pill: 999 };
export declare const touch: { min: 48; primary: 56; rider: 64 };
export declare const font: {
  /** Inter, every role */
  text: string;
  /** the same family as text (older imports) */
  display: string;
  scripts: { devanagari: string; telugu: string; tamil: string; kannada: string; bengali: string };
};
/** The fluid range: sizes run from min at minWidth to max at maxWidth (px on the web, dp in the apps). */
export declare const fluid: { minWidth: 360; maxWidth: 1440 };
export type TypeRole = "display" | "h1" | "h2" | "h3" | "body-lg" | "body" | "label" | "small" | "caption";
export type TypeToken = {
  /** px at a 360 px viewport */
  min: number;
  /** px at a 1440 px viewport */
  max: number;
  weight: "400" | "600" | "700";
  /** unitless multiplier */
  lineHeight: number;
  /** px */
  tracking: number;
  /** em (caption) */
  trackingEm?: number;
  uppercase?: true;
};
export declare const typeScale: Record<TypeRole, TypeToken>;
/** The size of a role in px at a viewport width (min at 360, max at 1440, linear between). */
export declare function fontSizeAt(role: TypeRole, width: number): number;
/** Each role's [min, max] in px. */
export declare const fontSizeRanges: Record<TypeRole, [number, number]>;
/** The smallest readable size (13); only the uppercase caption (12) is under it. */
export declare const minReadable: number;
type Type = { size: number; weight: "400" | "500" | "600" | "700" | "800"; tracking: number; family: "display" | "text" };
export declare const type: Record<"hero" | "h1" | "h2" | "title" | "body" | "label" | "small" | "tag" | "eyebrow", Type>;
export declare const shadow: { float: string; sheet: string; bar: string };
export declare const layout: {
  phone: { columns: number; edge: number; gap: number };
  tablet: { columns: number; edge: number; gap: number };
  web: { columns: number; edge: number; gap: number; maxWidth: number; sideMenu: number };
  page: { maxWidth: number; gutter: { phone: number; tablet: number; desktop: number } };
};
