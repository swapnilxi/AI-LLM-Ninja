export type Theme = "light" | "dark" | "system";
const KEY = "rag.theme";

export function getTheme(): Theme {
  try {
    const t = localStorage.getItem(KEY);
    if (t === "light" || t === "dark" || t === "system") return t;
  } catch {}
  return "system";
}

/** Sets <html data-theme="light|dark"> and remembers the choice. (layout.tsx runs the same logic before paint.) */
export function applyTheme(t: Theme): void {
  const dark = t === "dark" || (t === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  try {
    localStorage.setItem(KEY, t);
  } catch {}
}
