// Icons from the design (docs/design/web/*.html), same paths and strokes.
import type { SVGProps } from "react";

type P = SVGProps<SVGSVGElement> & { size?: number; color?: string; width2?: number };

function Svg({ size = 16, color = "currentColor", width2 = 2, children, ...rest }: P & { children: React.ReactNode }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={width2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...rest}>
      {children}
    </svg>
  );
}

export const Pin = (p: P) => (
  <Svg width2={2.2} {...p}>
    <path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z" />
    <circle cx="12" cy="9.5" r="2.5" />
  </Svg>
);
export const Chevron = (p: P) => (
  <Svg size={12} width2={2.6} {...p}>
    <path d="m6 9 6 6 6-6" />
  </Svg>
);
export const ChevronRight = (p: P) => (
  <Svg size={16} width2={2.4} {...p}>
    <path d="m9 6 6 6-6 6" />
  </Svg>
);
export const Globe = (p: P) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M3 12h18M12 3c3 3.5 3 14.5 0 18M12 3c-3 3.5-3 14.5 0 18" />
  </Svg>
);
export const Search = (p: P) => (
  <Svg size={18} width2={2.2} {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </Svg>
);
export const BagIcon = (p: P) => (
  <Svg size={18} {...p}>
    <path d="M6 8h12l-1 12H7L6 8z" />
    <path d="M9 8V6a3 3 0 0 1 6 0v2" />
  </Svg>
);
export const Heart = ({ filled, ...p }: P & { filled?: boolean }) => (
  <Svg size={16} width2={2.2} fill={filled ? "currentColor" : "none"} {...p}>
    <path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" />
  </Svg>
);
export const Locate = (p: P) => (
  <Svg size={16} {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
  </Svg>
);
export const Check = (p: P) => (
  <Svg size={14} width2={2.6} {...p}>
    <path d="m5 12 5 5 9-10" />
  </Svg>
);
export const Close = (p: P) => (
  <Svg size={18} width2={2.4} {...p}>
    <path d="M6 6l12 12M18 6 6 18" />
  </Svg>
);
export const Plus = (p: P) => (
  <Svg size={14} width2={2.6} {...p}>
    <path d="M12 5v14M5 12h14" />
  </Svg>
);
export const Minus = (p: P) => (
  <Svg size={14} width2={2.6} {...p}>
    <path d="M5 12h14" />
  </Svg>
);
export const Star = (p: P) => (
  <Svg size={14} fill="currentColor" width2={1} {...p}>
    <path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z" />
  </Svg>
);
export const Clock = (p: P) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </Svg>
);
export const Download = (p: P) => (
  <Svg {...p}>
    <path d="M12 4v11M7 10l5 5 5-5M5 20h14" />
  </Svg>
);
export const Share = (p: P) => (
  <Svg {...p}>
    <path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7M16 6l-4-4-4 4M12 2v14" />
  </Svg>
);

/** BhojanGo mark (the design's logo SVG). */
export const HomeIcon = (p: P) => (
  <Svg size={22} {...p}>
    <path d="M4 10.5 12 4l8 6.5V20h-5v-6H9v6H4z" />
  </Svg>
);
export const ReceiptIcon = (p: P) => (
  <Svg size={22} {...p}>
    <path d="M6 3h12v18l-3-2-3 2-3-2-3 2z" />
    <path d="M9 8h6M9 12h6" />
  </Svg>
);
export const UserIcon = (p: P) => (
  <Svg size={22} {...p}>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6" />
  </Svg>
);

export function LogoMark({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true">
      <path d="M11 5.5v24" stroke="#0B5D66" strokeWidth="5" strokeLinecap="round" fill="none" />
      <circle cx="20.5" cy="25" r="8.5" fill="none" stroke="#0B5D66" strokeWidth="5" />
      <path d="M18.5 13.5c-1.6-1.8 1.6-3.4 0-5.6M24.5 13.5c-1.6-1.8 1.6-3.4 0-5.6" stroke="#D4932A" strokeWidth="2.2" strokeLinecap="round" fill="none" />
    </svg>
  );
}
