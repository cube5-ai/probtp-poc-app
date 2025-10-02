import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Firebase Hosting with frameworksBackend handles Next.js automatically
  // No output needed - it will use the default Next.js build

  // Disable image optimization for Firebase Hosting compatibility
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
