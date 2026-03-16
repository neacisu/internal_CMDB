import type { NextConfig } from "next";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:4444";

const nextConfig: NextConfig = {
  output: process.env.NEXT_BUILD_STANDALONE === "1" ? "standalone" : undefined,
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
