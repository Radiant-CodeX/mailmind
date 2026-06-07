import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Allow the dev server to be opened via 127.0.0.1 (not just localhost) so
  // HMR and dev resources aren't blocked.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
};

export default nextConfig;
