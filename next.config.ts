import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const nextConfig: NextConfig = {
  // One container image per Section 3
  output: "standalone",
  eslint: {
    // Lint runs as its own CI step (lint → typecheck → test → build)
    ignoreDuringBuilds: true,
  },
};

export default withNextIntl(nextConfig);
