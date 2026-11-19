import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  /**
   * Same-origin API proxy: when API_PROXY_ORIGIN is set (Vercel build),
   * /api/* is forwarded to the backend so the browser only ever talks to
   * one origin — the httpOnly session cookie stays same-site and no CORS
   * configuration is needed. Local development leaves it unset and talks
   * to localhost:8000 directly.
   */
  async rewrites() {
    const origin = process.env.API_PROXY_ORIGIN?.trim().replace(/\/+$/, "");
    if (!origin) return [];
    return [{ source: "/api/:path*", destination: `${origin}/api/:path*` }];
  },
};

export default nextConfig;
