import axios from "axios";
import { deleteCookie } from "@/lib/cookies";

const API_BASE_URL =
	process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const api = axios.create({
	baseURL: API_BASE_URL,
	headers: {
		"Content-Type": "application/json",
	},
});

// Request interceptor to add auth token
api.interceptors.request.use(
	(config) => {
		const token = localStorage.getItem("access_token");
		if (token) {
			config.headers.Authorization = `Bearer ${token}`;
		}
		return config;
	},
	(error) => {
		return Promise.reject(error);
	},
);

// Response interceptor to handle token refresh
api.interceptors.response.use(
	(response) => {
		return response;
	},
	async (error) => {
		const originalRequest = error.config;

		// If error is 401 and we haven't tried to refresh yet
		if (error.response?.status === 401 && !originalRequest._retry) {
			originalRequest._retry = true;

			const refreshToken = localStorage.getItem("refresh_token");
			if (refreshToken) {
				try {
					const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
						refresh_token: refreshToken,
					});

					const { access_token, refresh_token: newRefreshToken } =
						response.data;

					localStorage.setItem("access_token", access_token);
					localStorage.setItem("refresh_token", newRefreshToken);

					// Retry original request with new token
					originalRequest.headers.Authorization = `Bearer ${access_token}`;
					return api(originalRequest);
				} catch (refreshError) {
					// Refresh failed, clear tokens and redirect to login
					localStorage.removeItem("access_token");
					localStorage.removeItem("refresh_token");
					deleteCookie("is_authenticated");
					window.location.href = "/";
					return Promise.reject(refreshError);
				}
			}
		}

		return Promise.reject(error);
	},
);

// API endpoints
export const authApi = {
	getLoginUrl: () => api.get<{ auth_url: string }>("/auth/youtube/login"),
	getCurrentUser: () => api.get("/auth/me"),
	refreshToken: (refreshToken: string) =>
		api.post("/auth/refresh", { refresh_token: refreshToken }),
};

export const videosApi = {
	getLikedVideos: (params?: {
		cursor?: string;
		limit?: number;
		category_ids?: string;
		tag_ids?: string;
		search?: string;
		is_categorized?: boolean;
		sort_by?: string;
		sort_order?: string;
	}) => api.get("/videos/liked", { params }),

	getWatchLaterVideos: (params?: {
		cursor?: string;
		limit?: number;
		category_ids?: string;
		tag_ids?: string;
		search?: string;
		is_categorized?: boolean;
		sort_by?: string;
		sort_order?: string;
	}) => api.get("/videos/watch-later", { params }),

	syncVideos: (params?: { max_results?: number }) =>
		api.post("/videos/sync", null, { params }),

	syncWatchLaterVideos: (params?: { max_results?: number }) =>
		api.post("/videos/sync/watch-later", null, { params }),

	syncWatchLaterBatch: (params?: { auto_categorize?: boolean }) =>
		api.post("/videos/sync/watch-later/batch", null, { params }),

	syncBatch: (params?: { auto_categorize?: boolean }) =>
		api.post("/videos/sync/batch", null, { params }),

	startBatchCategorization: (params?: {
		max_concurrent?: number;
		max_videos?: number;
	}) => api.post("/videos/categorize-batch/start", null, { params }),

	getBatchResult: (jobId: string) =>
		api.get(`/videos/categorize-batch/result/${jobId}`),

	pauseCategorizationJob: (jobId: string) =>
		api.post(`/videos/categorize-batch/pause/${jobId}`),

	resumeCategorizationJob: (jobId: string) =>
		api.post(`/videos/categorize-batch/resume/${jobId}`),

	cancelCategorizationJob: (jobId: string) =>
		api.post(`/videos/categorize-batch/cancel/${jobId}`),

	categorizeVideo: (videoId: number) =>
		api.post(`/videos/${videoId}/categorize`),

	searchVideos: (params: { q: string; page?: number; page_size?: number }) =>
		api.get("/videos/search", { params }),

	getVideoStats: () => api.get("/videos/stats"),

	getVideo: (videoId: number) => api.get(`/videos/${videoId}`),

	// Delete by tags
	getVideoCountByTags: (tagIds: number[]) =>
		api.get("/videos/count-by-tags", { params: { tag_ids: tagIds.join(",") } }),

	startDeleteByTags: (tagIds: number[]) =>
		api.post("/videos/delete-by-tags/start", null, {
			params: { tag_ids: tagIds.join(",") },
		}),

	getDeleteResult: (jobId: string) =>
		api.get(`/videos/delete-by-tags/result/${jobId}`),

	cancelDeleteJob: (jobId: string) =>
		api.post(`/videos/delete-by-tags/cancel/${jobId}`),

	// Semantic search
	semanticSearch: (params: {
		q: string;
		limit?: number;
		similarity_threshold?: number;
	}) => api.get("/videos/semantic-search", { params }),

	// Embeddings
	getEmbeddingStats: () => api.get("/videos/embeddings/stats"),

	generateEmbeddings: (params?: {
		max_videos?: number;
		max_concurrent?: number;
	}) => api.post("/videos/embeddings/generate", null, { params }),

	// Embedding generation with SSE progress
	startEmbeddingGeneration: (params?: {
		max_videos?: number;
		max_concurrent?: number;
		force_regenerate?: boolean;
	}) => api.post("/videos/embeddings/generate/start", null, { params }),
};

export const playlistsApi = {
	getPlaylists: (params?: { page?: number; page_size?: number }) =>
		api.get("/playlists", { params }),

	getPlaylist: (playlistId: number) => api.get(`/playlists/${playlistId}`),

	getPlaylistVideos: (
		playlistId: number,
		params?: {
			cursor?: string;
			limit?: number;
			category_ids?: string;
			tag_ids?: string;
			search?: string;
		},
	) => api.get(`/playlists/${playlistId}/videos`, { params }),

	syncPlaylists: (params?: { max_results?: number }) =>
		api.post("/playlists/sync", null, { params }),

	syncPlaylistVideos: (
		playlistId: number,
		params?: { max_results?: number; auto_categorize?: boolean },
	) => api.post(`/playlists/${playlistId}/sync-videos`, null, { params }),

	createFromFilters: (data: {
		title: string;
		description?: string;
		privacy_status?: string;
		filter_params: {
			category_ids?: number[];
			tag_ids?: number[];
			search?: string;
			is_categorized?: boolean;
		};
	}) => api.post("/playlists/create-from-filters", data),
};

export const categoriesApi = {
	getCategories: () => api.get("/categories/"),
	getCategoryVideos: (
		categoryId: number,
		params?: { page?: number; page_size?: number },
	) => api.get(`/categories/${categoryId}/videos/`, { params }),
};

export const tagsApi = {
	getTags: (params?: { min_usage?: number; limit?: number }) =>
		api.get("/tags/", { params }),

	getTagCloud: (params?: { limit?: number }) =>
		api.get("/tags/cloud/", { params }),

	getTagVideos: (
		tagId: number,
		params?: { page?: number; page_size?: number },
	) => api.get(`/tags/${tagId}/videos/`, { params }),
};

export const insightsApi = {
	getOverview: (params?: { force_refresh?: boolean }) =>
		api.get("/insights/overview", { params }),

	getContentDistribution: (params?: { force_refresh?: boolean }) =>
		api.get("/insights/content-distribution", { params }),

	getChannels: (params?: { limit?: number; force_refresh?: boolean }) =>
		api.get("/insights/channels", { params }),

	getTemporal: (params?: { force_refresh?: boolean }) =>
		api.get("/insights/temporal", { params }),

	getDuration: (params?: { force_refresh?: boolean }) =>
		api.get("/insights/duration", { params }),

	getRecommendations: (params?: { limit?: number; force_refresh?: boolean }) =>
		api.get("/insights/recommendations", { params }),
};
