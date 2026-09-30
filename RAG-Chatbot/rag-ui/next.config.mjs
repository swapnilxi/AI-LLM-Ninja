const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

/** @type {import('next').NextConfig} */
export default {
  // keep the dev-mode badge out of the sidebar footer (theme toggle / status live bottom-left)
  devIndicators: { position: "bottom-right" },
  // The browser talks to /api/* on the Next server, which forwards to the FastAPI backend.
  // No CORS setup needed and the backend URL stays server-side.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND}/api/:path*` }];
  },
};
