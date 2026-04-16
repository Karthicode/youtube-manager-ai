export const swrKeys = {
	videoStats: () => "/videos/stats",
	categories: () => "/categories/",
	tags: (params?: { limit?: number }) =>
		params ? (["/tags/", params] as const) : "/tags/",
	playlists: (params?: { page?: number; page_size?: number }) =>
		params ? (["/playlists/", params] as const) : "/playlists/",
	chatSessions: () => "/chat/sessions",
	preferences: () => "/preferences",
	continueWatching: (limit?: number) =>
		limit
			? (["/watch-history/continue-watching", { limit }] as const)
			: "/watch-history/continue-watching",
	insightsOverview: () => "/insights/overview",
	insightsContentDist: () => "/insights/content-distribution",
	insightsChannels: (limit?: number) =>
		limit ? (["/insights/channels", { limit }] as const) : "/insights/channels",
	insightsTemporal: () => "/insights/temporal",
	insightsDuration: () => "/insights/duration",
	insightsRecommendations: (limit?: number) =>
		limit
			? (["/insights/recommendations", { limit }] as const)
			: "/insights/recommendations",
	autoCategorizeStatus: () => "/cron/auto-categorize/status/me",
};
