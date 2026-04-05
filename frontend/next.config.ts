import type { NextConfig } from "next";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:4444";

const nextConfig: NextConfig = {
  output: process.env.NEXT_BUILD_STANDALONE === "1" ? "standalone" : undefined,
  // Allow the public reverse-proxy domain to access /_next/* dev resources.
  // Without this, Next.js 16+ will block cross-origin HMR and chunk requests
  // when the dev server is accessed via a domain other than localhost.
  // Ref: https://nextjs.org/docs/app/api-reference/config/next-config-js/allowedDevOrigins
  allowedDevOrigins: ["infraq.app", "www.infraq.app"],
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${BACKEND_URL}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
