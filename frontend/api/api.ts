import axios from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

console.log("🔧 API Base URL:", API_BASE_URL);

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    console.log("📤 API Request:", config.method?.toUpperCase(), config.url);
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    console.error("❌ Request Error:", error);
    return Promise.reject(error);
  }
);

// Response interceptor to handle token refresh
api.interceptors.response.use(
  (response) => {
    console.log("✅ API Response:", response.config.method?.toUpperCase(), response.config.url, response.status);
    return response;
  },
  async (error) => {
    console.error("❌ API Error:", error.config?.url, error.response?.status, error.message);
    console.error("Full error:", error.response?.data || error.message);

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

          const { access_token, refresh_token: newRefreshToken } = response.data;

          localStorage.setItem("access_token", access_token);
          localStorage.setItem("refresh_token", newRefreshToken);

          // Retry original request with new token
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return api(originalRequest);
        } catch (refreshError) {
          // Refresh failed, clear tokens and redirect to login
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          window.location.href = "/";
          return Promise.reject(refreshError);
        }
      }
    }

    return Promise.reject(error);
  }
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
    page?: number;
    page_size?: number;
    category_ids?: string;
    tag_ids?: string;
    search?: string;
    is_categorized?: boolean;
    sort_by?: string;
    sort_order?: string;
  }) => api.get("/videos/liked", { params }),

  syncVideos: (params?: { max_results?: number; auto_categorize?: boolean }) =>
    api.post("/videos/sync", null, { params }),

  syncBatch: (params?: { auto_categorize?: boolean }) =>
    api.post("/videos/sync/batch", null, { params }),

  categorizeBatch: (params?: { batch_size?: number; max_videos?: number }) =>
    api.post("/videos/categorize-batch", null, { params }),

  categorizeVideo: (videoId: number) =>
    api.post(`/videos/${videoId}/categorize`),

  searchVideos: (params: { q: string; page?: number; page_size?: number }) =>
    api.get("/videos/search", { params }),

  getVideoStats: () => api.get("/videos/stats"),

  getVideo: (videoId: number) => api.get(`/videos/${videoId}`),
};

export const playlistsApi = {
  getPlaylists: (params?: { page?: number; page_size?: number }) =>
    api.get("/playlists", { params }),

  getPlaylist: (playlistId: number) =>
    api.get(`/playlists/${playlistId}`),

  getPlaylistVideos: (
    playlistId: number,
    params?: {
      page?: number;
      page_size?: number;
      category_ids?: string;
      tag_ids?: string;
      search?: string;
    }
  ) => api.get(`/playlists/${playlistId}/videos`, { params }),

  syncPlaylists: (params?: { max_results?: number }) =>
    api.post("/playlists/sync", null, { params }),

  syncPlaylistVideos: (
    playlistId: number,
    params?: { max_results?: number; auto_categorize?: boolean }
  ) => api.post(`/playlists/${playlistId}/sync-videos`, null, { params }),
};

export const categoriesApi = {
  getCategories: () => api.get("/categories/"),
  getCategoryVideos: (categoryId: number, params?: { page?: number; page_size?: number }) =>
    api.get(`/categories/${categoryId}/videos/`, { params }),
};

export const tagsApi = {
  getTags: (params?: { min_usage?: number; limit?: number }) =>
    api.get("/tags/", { params }),

  getTagCloud: (params?: { limit?: number }) =>
    api.get("/tags/cloud/", { params }),

  getTagVideos: (tagId: number, params?: { page?: number; page_size?: number }) =>
    api.get(`/tags/${tagId}/videos/`, { params }),
};
