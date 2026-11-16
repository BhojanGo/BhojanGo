"use client";
// The table of contents' links, with the section you're reading marked (desktop's
// sticky list). Without JavaScript they are plain links to the headings.
import { useEffect, useState } from "react";

export function TocLinks({ items, spy = false }: { items: { id: string; text: string }[]; spy?: boolean }) {
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    if (!spy) return;
    const headings = items.map((s) => document.getElementById(s.id)).filter((h): h is HTMLElement => Boolean(h));
    let frame = 0;
    // The section you're in: the last heading above the upper third of the window.
    const update = () => {
      frame = 0;
      const line = window.innerHeight / 3;
      const current = [...headings].reverse().find((h) => h.getBoundingClientRect().top <= line);
      setActive(current?.id ?? null);
    };
    const onScroll = () => { if (!frame) frame = requestAnimationFrame(update); };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [items, spy]);

  return (
    <ol className="space-y-1">
      {items.map((s) => {
        const on = spy && s.id === active;
        return (
          <li key={s.id}>
            <a href={`#${s.id}`} aria-current={on ? "location" : undefined}
              className={`block rounded-lg border-l-[3px] px-3 py-2 text-small leading-snug focus-visible:outline focus-visible:outline-2 focus-visible:outline-peacock ${on
                ? "border-peacock bg-[#EFF6F6] font-semibold text-peacock-deep" : "border-transparent text-muted hover:bg-porcelain hover:text-peacock"}`}>
              {s.text}
            </a>
          </li>
        );
      })}
    </ol>
  );
}
