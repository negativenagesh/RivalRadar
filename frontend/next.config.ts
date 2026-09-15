import type { NextConfig } from "next";

// Docker / self-host needs standalone. On Vercel + Next 16.3, standalone + the
// injected adapter fails with ENOENT .next/next-server.js.nft.json.
const nextConfig: NextConfig = {
  output: process.env.VERCEL ? undefined : "standalone",
};

export default nextConfig;
