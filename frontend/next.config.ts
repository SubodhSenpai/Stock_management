import type { NextConfig } from "next";

/**
 * The browser talks to the API directly (CORS is configured for this origin on the
 * backend), so there is no rewrite here: one fewer hop, and the session cookies stay
 * first-party because both processes are served from the same host.
 */
const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  output: "standalone",
  eslint: {
    dirs: ["src"],
  },
};

export default nextConfig;
