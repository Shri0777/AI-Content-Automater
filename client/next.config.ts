import type { NextConfig } from "next";

/*
 * cacheComponents and partialPrefetching (the scaffold's defaults) are off:
 * every page here depends on who is signed in, and all data comes from the
 * Django API with a token kept only in the browser, so there is nothing to
 * prerender or cache on the Next.js server.
 */
const nextConfig: NextConfig = {
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
