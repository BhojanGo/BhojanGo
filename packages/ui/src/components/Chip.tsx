import * as React from "react";
import { cn } from "../lib/utils";

export interface ChipProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  selected?: boolean;
  /** count badge, e.g. cities needing attention */
  count?: number;
}

/** Filter or choice chip: 8 px radius, 40 px tall, at least a 48 px hit area. */
export function Chip({ selected, count, className, children, ...rest }: ChipProps) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      className={cn(
        "inline-flex h-10 items-center gap-2 rounded-chip border px-3 text-sm font-semibold",
        selected ? "border-peacock bg-peacock-tint font-extrabold text-peacock-deep" : "border-line bg-white text-kohl hover:border-line-strong",
        className,
      )}
      {...rest}
    >
      {children}
      {count != null && (
        <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-pill bg-kesar px-1 text-[11px] font-extrabold text-kohl">{count}</span>
      )}
    </button>
  );
}

/** A segmented choice like the tip picker: one pill track, the chosen one raised. */
export function Segmented<T extends string>({ options, value, onChange, label }: {
  options: { value: T; label: string }[]; value: T; onChange: (v: T) => void; label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex rounded-pill bg-porcelain p-1">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={o.value === value}
          onClick={() => onChange(o.value)}
          className={cn("h-[42px] flex-1 rounded-pill text-[15px]",
            o.value === value ? "bg-white font-extrabold text-kohl shadow-[0_1px_3px_rgba(17,20,24,0.12)]" : "font-semibold text-muted")}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
