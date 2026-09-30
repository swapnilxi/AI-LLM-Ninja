import type { Metadata, Viewport } from "next";
import "./globals.css";
import LiquidLight from "@/components/LiquidLight";

export const metadata: Metadata = { title: "RAG Chatbot", description: "Chat with your documents — configurable models and vector database" };
export const viewport: Viewport = { width: "device-width", initialScale: 1 };

// Runs before first paint so a dark-mode user never sees a white flash.
const THEME_INIT = `try{var t=localStorage.getItem('rag.theme')||'system';var d=t==='dark'||(t==='system'&&matchMedia('(prefers-color-scheme: dark)').matches);document.documentElement.dataset.theme=d?'dark':'light'}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT }} />
      </head>
      <body>
        {/* refraction lens used by backdrop-filter: url(#lens) in globals.css (Chromium) */}
        <svg width="0" height="0" style={{ position: "absolute" }} aria-hidden>
          <filter id="lens" x="0" y="0" width="100%" height="100%">
            <feTurbulence type="fractalNoise" baseFrequency="0.006 0.01" numOctaves="2" seed="7" result="n" />
            <feGaussianBlur in="n" stdDeviation="4" result="nb" />
            <feDisplacementMap in="SourceGraphic" in2="nb" scale="34" xChannelSelector="R" yChannelSelector="G" />
          </filter>
        </svg>
        <LiquidLight />
        {children}
      </body>
    </html>
  );
}
