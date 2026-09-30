"use client";

import { useEffect } from "react";

// Surfaces that get a specular highlight following the cursor (see .lg-light in globals.css).
const SELECTOR = ".sidebar, .header-status-badges, .composer, .card, .tile, .status-card, .seg, .savebar, .drawer, .suggest-card, .toast, .banner";

/** Feeds --mx/--my (cursor position inside the hovered glass surface) so its highlight tracks the pointer. */
export default function LiquidLight() {
  useEffect(() => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let raf = 0;
    const move = (e: PointerEvent) => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const el = (e.target as Element | null)?.closest?.(SELECTOR) as HTMLElement | null;
        if (!el) return;
        const r = el.getBoundingClientRect();
        el.style.setProperty("--mx", `${e.clientX - r.left}px`);
        el.style.setProperty("--my", `${e.clientY - r.top}px`);
      });
    };
    addEventListener("pointermove", move, { passive: true });
    return () => { removeEventListener("pointermove", move); cancelAnimationFrame(raf); };
  }, []);
  return null;
}
