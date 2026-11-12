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
export declare const font: { display: string; text: string };
type Type = { size: number; weight: "400" | "500" | "600" | "700" | "800"; tracking: number; family: "display" | "text" };
export declare const type: Record<"hero" | "h1" | "h2" | "title" | "body" | "label" | "small" | "tag" | "eyebrow", Type>;
export declare const shadow: { float: string; sheet: string; bar: string };
export declare const layout: {
  phone: { columns: number; edge: number; gap: number };
  tablet: { columns: number; edge: number; gap: number };
  web: { columns: number; edge: number; gap: number; maxWidth: number; sideMenu: number };
};
