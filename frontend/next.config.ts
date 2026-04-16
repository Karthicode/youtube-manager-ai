import type { NextConfig } from "next";

const nextConfig: NextConfig = {
	reactStrictMode: true,
	// Unified PPR + dynamic IO flag (Next 16+). Required for the `'use cache'`
	// directive. Most pages are currently client-rendered (JWT lives in
	// localStorage), so this is a no-op for them; it enables future Server
	// Component caching without forcing anything on existing client pages.
	cacheComponents: true,
	images: {
		remotePatterns: [
			{
				protocol: "https",
				hostname: "i.ytimg.com",
			},
			{
				protocol: "https",
				hostname: "yt3.ggpht.com",
			},
		],
	},
};

export default nextConfig;
