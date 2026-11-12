import * as React from "react";
import { cn } from "../lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** kesar = offers and stars; dark = on photos; neutral = facts; alert = Chili, alerts only */
  variant?: "neutral" | "kesar" | "dark" | "peacock" | "alert";
}

const styles = {
  neutral: "bg-porcelain text-kohl",
  kesar: "bg-kesar text-kohl",
  dark: "bg-kohl text-white",
  peacock: "bg-peacock-tint text-peacock-deep",
  alert: "bg-chili text-white",
} as const;

export function Badge({ variant = "neutral", className, ...rest }: BadgeProps) {
  return <span className={cn("inline-flex items-center rounded-pill px-2.5 py-1.5 text-xs font-bold", styles[variant], className)} {...rest} />;
}

export const badgeVariants = (v: NonNullable<BadgeProps["variant"]> = "neutral") => styles[v];
