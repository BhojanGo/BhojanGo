"use client";
// R39: nothing on a phone page is ever hidden behind a bar pinned to the bottom of the screen.
//  - useFitBelowHeader: checkout. The page fills the screen below the sticky header; its content scrolls
//    inside and the Pay bar sits under it (a flex column), so no text can pass behind the button.
//  - useReserveBottom: a floating bar over a long page (a restaurant's "View cart"). The page gets bottom
//    padding equal to the bar's height and its gap to the screen edge, so the last thing on it ends above the bar.
import { useEffect, useState, type RefObject } from "react";

const PHONE = "(max-width: 767.98px)";

/** The height (px) that fills the screen from below the header on a phone; null on wider screens. */
export function useFitBelowHeader(ref: RefObject<HTMLElement | null>): number | null {
  const [height, setHeight] = useState<number | null>(null);
  useEffect(() => {
    const mq = window.matchMedia(PHONE);
    let frame = 0;
    const fit = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const el = ref.current;
        if (!el || !mq.matches) return setHeight(null);
        const header = document.querySelector("header");
        const under = header ? header.getBoundingClientRect().bottom : 0;
        // Banners above the header scroll away: until they do the box starts lower (and is shorter).
        const top = Math.max(under, el.getBoundingClientRect().top);
        const next = Math.max(320, Math.floor(window.innerHeight - top));
        setHeight((h) => (h === next ? h : next));
      });
    };
    fit();
    window.addEventListener("resize", fit);
    window.addEventListener("scroll", fit, { passive: true });
    mq.addEventListener("change", fit);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", fit);
      window.removeEventListener("scroll", fit);
      mq.removeEventListener("change", fit);
    };
  }, [ref]);
  return height;
}

/** While ``active``, pad the page's bottom by the pinned bar's height and its gap to the bottom edge. */
export function useReserveBottom(ref: RefObject<HTMLElement | null>, active: boolean): void {
  useEffect(() => {
    const el = ref.current;
    if (!active || !el) return;
    const body = document.body;
    const before = body.style.paddingBottom;
    const measure = () => {
      const shown = getComputedStyle(el).position === "fixed" && el.offsetParent !== null;
      if (!shown) {
        body.style.paddingBottom = before;
        return;
      }
      const r = el.getBoundingClientRect();
      const gap = Math.max(0, window.innerHeight - r.bottom);
      body.style.paddingBottom = `${Math.ceil(r.height + gap * 2)}px`;
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    window.addEventListener("resize", measure);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", measure);
      body.style.paddingBottom = before;
    };
  }, [ref, active]);
}
