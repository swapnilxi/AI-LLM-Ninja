export type Theme = "light" | "dark" | "system";
export type AccentColor = "blue" | "purple" | "emerald" | "amber" | "rose" | "graphite" | "cyan" | "indigo" | "orange" | "lime" | "crimson" | "gold";

export interface AccentOption {
  id: AccentColor;
  label: string;
  lightHex: string;
  darkHex: string;
}

export const ACCENTS: AccentOption[] = [
  { id: "blue",     label: "Apple Blue",      lightHex: "#0071e3", darkHex: "#2997ff" },
  { id: "purple",   label: "Vision Violet",   lightHex: "#8e44ad", darkHex: "#bf5af2" },
  { id: "cyan",     label: "Ocean Cyan",      lightHex: "#0891b2", darkHex: "#22d3ee" },
  { id: "indigo",   label: "Midnight Indigo", lightHex: "#4338ca", darkHex: "#818cf8" },
  { id: "emerald",  label: "Emerald Mint",    lightHex: "#059669", darkHex: "#30d158" },
  { id: "lime",     label: "Electric Lime",   lightHex: "#65a30d", darkHex: "#a3e635" },
  { id: "amber",    label: "Amber Sunset",    lightHex: "#d97706", darkHex: "#ff9f0a" },
  { id: "orange",   label: "Burnt Orange",    lightHex: "#ea580c", darkHex: "#fb923c" },
  { id: "gold",     label: "Warm Gold",       lightHex: "#a16207", darkHex: "#fbbf24" },
  { id: "rose",     label: "Rose Coral",      lightHex: "#e11d48", darkHex: "#ff375f" },
  { id: "crimson",  label: "Deep Crimson",    lightHex: "#be185d", darkHex: "#f472b6" },
  { id: "graphite", label: "Titanium Slate",  lightHex: "#475569", darkHex: "#94a3b8" },
];

const THEME_KEY = "rag.theme";
const ACCENT_KEY = "rag.accent";

/** Get theme for a specific profile, falling back to global theme or system */
export function getProfileTheme(profileId?: string): Theme {
  try {
    if (profileId) {
      const p = localStorage.getItem(`${THEME_KEY}.${profileId}`);
      if (p === "light" || p === "dark" || p === "system") return p;
    }
    const t = localStorage.getItem(THEME_KEY);
    if (t === "light" || t === "dark" || t === "system") return t;
  } catch {}
  return "system";
}

/** Get accent color for a specific profile, falling back to global accent or blue */
export function getProfileAccent(profileId?: string): AccentColor {
  try {
    if (profileId) {
      const p = localStorage.getItem(`${ACCENT_KEY}.${profileId}`);
      if (ACCENTS.some((a) => a.id === p)) return p as AccentColor;
    }
    const a = localStorage.getItem(ACCENT_KEY);
    if (ACCENTS.some((ac) => ac.id === a)) return a as AccentColor;
  } catch {}
  return "blue";
}

/** Apply theme and accent color to the document and persist */
export function applyAppearance(profileId?: string, theme?: Theme, accent?: AccentColor): void {
  const currentTheme = theme ?? getProfileTheme(profileId);
  const currentAccent = accent ?? getProfileAccent(profileId);

  const dark = currentTheme === "dark" || (currentTheme === "system" && typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  if (typeof document !== "undefined") {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    document.documentElement.dataset.accent = currentAccent;
  }

  try {
    if (theme) {
      if (profileId) localStorage.setItem(`${THEME_KEY}.${profileId}`, theme);
      localStorage.setItem(THEME_KEY, theme);
    }
    if (accent) {
      if (profileId) localStorage.setItem(`${ACCENT_KEY}.${profileId}`, accent);
      localStorage.setItem(ACCENT_KEY, accent);
    }
  } catch {}
}

// Backward-compatible helpers
export const getTheme = (profileId?: string) => getProfileTheme(profileId);
export const applyTheme = (t: Theme, profileId?: string) => applyAppearance(profileId, t);

