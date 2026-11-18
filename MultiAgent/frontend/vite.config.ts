import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    port: 5173,
    // startup.sh passes AGENTFORGE_API_PORT when the API runs on a non-default port
    proxy: { "/api": { target: `http://127.0.0.1:${process.env.AGENTFORGE_API_PORT ?? "8000"}`, changeOrigin: false } },
  },
  build: { chunkSizeWarningLimit: 1500 },
});
