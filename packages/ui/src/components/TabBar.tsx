import * as React from "react";
import { cn } from "../lib/utils";

export interface TabItem {
  key: string;
  label: string;
  icon: React.ReactNode;
  href?: string;
}

/** The floating dark pill at the bottom of customer screens: the current tab
 * shows its label on Peacock, the others are icons (each still labelled). */
export function TabBar({ items, current, onSelect, className }: {
  items: TabItem[];
  current: string;
  onSelect?: (key: string) => void;
  className?: string;
}) {
  return (
    <nav aria-label="Main" className={cn("flex h-16 items-center gap-1 rounded-pill bg-kohl px-2 shadow-bar", className)}>
      {items.map((t) => {
        const active = t.key === current;
        const cls = cn(
          "flex h-12 items-center justify-center gap-2 rounded-pill text-sm font-bold",
          active ? "bg-peacock px-[18px] text-white" : "w-[52px] text-line-strong hover:text-white",
        );
        const body = (
          <>
            {t.icon}
            {active && <span>{t.label}</span>}
          </>
        );
        return t.href ? (
          <a key={t.key} href={t.href} aria-label={t.label} aria-current={active ? "page" : undefined} className={cls}>
            {body}
          </a>
        ) : (
          <button key={t.key} type="button" aria-label={t.label} aria-pressed={active} onClick={() => onSelect?.(t.key)} className={cls}>
            {body}
          </button>
        );
      })}
    </nav>
  );
}
