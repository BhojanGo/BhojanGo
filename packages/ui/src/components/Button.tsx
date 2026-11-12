import * as React from "react";
import { cn } from "../lib/utils";

type Variant = "primary" | "secondary" | "ghost" | "rider" | "danger";
type Size = "md" | "lg";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  /** md = 48 px (any control), lg = 56 px (the screen's main action). */
  size?: Size;
  block?: boolean;
  loading?: boolean;
}

const variants: Record<Variant, string> = {
  primary: "bg-peacock text-white hover:bg-peacock-deep",
  secondary: "bg-white text-kohl border-[1.5px] border-line-strong hover:border-peacock",
  ghost: "bg-transparent text-peacock hover:bg-peacock-mist",
  rider: "bg-kesar-bright text-kohl", // rider app: 64 px, Kesar
  danger: "bg-chili text-white",
};

/** Pill button. Primary is Peacock; Kesar is only for the rider's main action. */
export function Button({ variant = "primary", size = "md", block, loading, className, children, disabled, ...rest }: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-pill px-6 font-extrabold tabular-nums transition-colors",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peacock",
        "disabled:cursor-not-allowed disabled:opacity-50",
        size === "lg" ? "h-14 text-[17px]" : "h-12 text-[15px]",
        variant === "rider" && "h-16 text-lg",
        variants[variant],
        block && "w-full",
        className,
      )}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <span className="h-5 w-5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden /> : null}
      {children}
    </button>
  );
}
