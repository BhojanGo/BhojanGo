import * as React from "react";
import { cn } from "../lib/utils";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** flat = white on Porcelain (default), outline = hairline border, floating = shadow */
  tone?: "flat" | "outline" | "floating";
  padding?: "none" | "md" | "lg";
  hover?: boolean;
}

/** 16 px radius surface. Padding 16 on phones, 24 on tablet and web. */
export function Card({ tone = "flat", padding = "md", hover, className, ...rest }: CardProps) {
  return (
    <div
      className={cn(
        "rounded-card bg-white",
        tone === "outline" && "border border-line",
        tone === "floating" && "shadow-float",
        padding === "md" && "p-4",
        padding === "lg" && "p-6",
        hover && "transition-shadow hover:shadow-float",
        className,
      )}
      {...rest}
    />
  );
}

export const CardHeader = ({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) => <div className={cn("mb-3", className)} {...p} />;
export const CardTitle = ({ className, ...p }: React.HTMLAttributes<HTMLHeadingElement>) => (
  <h3 className={cn("font-display text-xl font-semibold tracking-[-0.3px]", className)} {...p} />
);
export const CardDescription = ({ className, ...p }: React.HTMLAttributes<HTMLParagraphElement>) => (
  <p className={cn("text-sm text-muted", className)} {...p} />
);
export const CardContent = (p: React.HTMLAttributes<HTMLDivElement>) => <div {...p} />;
export const CardFooter = ({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) => <div className={cn("mt-4 flex gap-3", className)} {...p} />;
