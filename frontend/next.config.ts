import type { NextConfig } from "next";

// Server-side proxy target. Prefer BACKEND_URL (not exposed to the browser) so
// the browser keeps calling same-origin /api/* and auth cookies stay first-party
// even when the backend lives on another domain (e.g. Render vs Vercel).
const BACKEND =
  process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND}/api/:path*`,
      },
    ];
  },
  async redirects() {
    return [
      // Common aliases for the legal pages.
      { source: "/tos", destination: "/terms", permanent: true },
      { source: "/privacy-policy", destination: "/privacy", permanent: true },
    ];
  },
};

export default nextConfig;
