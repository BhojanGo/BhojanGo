// A kitchen's picture (R8). The API's photo_url is already the best there is:
// the kitchen's own cover, else its first dish photo, else a photo of its cuisine
// from the food photo library (core_api catalog.service.photos). With none of
// those, a plain branded tile: the brand tint and a plate glyph, no text, so
// nothing is ever drawn on top of the kitchen's name (it was its initials).

/** photo_url, falling back to cover_url for an older API. */
export function kitchenPhoto(k: { photo_url?: string | null; cover_url?: string | null } | null | undefined): string | null {
  return k?.photo_url ?? k?.cover_url ?? null;
}

/** The plain tile for a kitchen with no photo at all. `glyph={false}` when text sits on top of it. */
export function BrandTile({ className, glyph = true }: { className?: string; glyph?: boolean }) {
  return (
    <span
      aria-hidden="true"
      data-testid="kitchen-tile"
      className={`flex items-center justify-center bg-[radial-gradient(circle_at_30%_25%,#EFF6F6_0%,#DDEBEC_60%,#CFE3E5_100%)] ${className ?? ""}`}
    >
      {glyph && (
        <svg viewBox="0 0 48 48" className="h-[42%] max-h-14 w-[42%] max-w-14" fill="none" stroke="#0B5D66" strokeOpacity="0.55" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="24" cy="24" r="12" />
          <circle cx="24" cy="24" r="7" strokeOpacity="0.35" />
          <path d="M6 10v9a3 3 0 0 0 6 0v-9M9 10v28M42 10c-4 3-4 11 0 14v14" />
        </svg>
      )}
    </span>
  );
}

/** A kitchen's photo filling its box, else the tile. `src` is already sized (format.photo). */
export function KitchenPhoto({ src, className, alt = "", glyph = true }: { src: string | null; className?: string; alt?: string; glyph?: boolean }) {
  if (!src) return <BrandTile className={className} glyph={glyph} />;
  // eslint-disable-next-line @next/next/no-img-element -- local WebP sizes from the photo library, already optimised
  return <img src={src} alt={alt} loading="lazy" className={`block object-cover ${className ?? ""}`} />;
}
