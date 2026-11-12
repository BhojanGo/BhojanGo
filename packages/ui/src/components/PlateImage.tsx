import * as React from "react";
import { cn } from "../lib/utils";

export interface PlateImageProps {
  /** A dish photo, shot overhead on a round plate. Without one, the drawn plate. */
  src?: string | null;
  alt: string;
  /** soft tinted ground behind the plate */
  ground?: string;
  size?: number;
  className?: string;
}

/** The plate frame: one art direction for every restaurant (Main.html). */
export function PlateImage({ src, alt, ground = "#F6E7CC", size = 96, className }: PlateImageProps) {
  return (
    <div className={cn("flex items-center justify-center overflow-hidden", className)} style={{ background: ground }}>
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt={alt} width={size} height={size} className="rounded-full object-cover" style={{ width: size, height: size }} />
      ) : (
        <PlateArt size={size} label={alt} />
      )}
    </div>
  );
}

export function PlateArt({ size = 96, label }: { size?: number; label?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 120 120" role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      <circle cx="60" cy="60" r="56" fill="#FFFFFF" stroke="#D5DEDF" strokeWidth="2" />
      <circle cx="60" cy="60" r="44" fill="#FBFAF7" />
      <ellipse cx="64" cy="66" rx="27" ry="21" fill="#E2B866" />
      <circle cx="56" cy="60" r="3" fill="#8A4B2A" />
      <circle cx="70" cy="70" r="3" fill="#8A4B2A" />
      <circle cx="66" cy="58" r="2.5" fill="#4F7F52" />
      <circle cx="35" cy="38" r="13" fill="#FFFFFF" stroke="#D5DEDF" strokeWidth="2" />
      <circle cx="35" cy="38" r="9" fill="#F1EFE8" />
    </svg>
  );
}
