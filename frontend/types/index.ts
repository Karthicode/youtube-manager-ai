export interface User {
	id: number;
	email: string;
	name: string;
	picture: string | null;
	youtube_channel_id: string | null;
	last_sync_at: string | null;
	created_at: string;
}

export interface Category {
	id: number;
	name: string;
	slug: string;
	description: string | null;
	color: string | null;
	icon: string | null;
	created_at: string;
}

export interface Tag {
	id: number;
	name: string;
	slug: string;
	usage_count: number;
	created_at: string;
}

export interface Video {
	id: number;
	youtube_id: string;
	title: string;
	description: string | null;
	thumbnail_url: string | null;
	channel_title: string | null;
	channel_id: string | null;
	duration_seconds: number | null;
	published_at: string | null;
	liked_at: string;
	view_count: number | null;
	like_count: number | null;
	is_categorized: boolean;
	categorized_at: string | null;
	categories: Category[];
	tags: Tag[];
	created_at: string;
	updated_at: string;
}

export interface Playlist {
	id: number;
	youtube_id: string;
	title: string;
	description: string | null;
	thumbnail_url: string | null;
	channel_title: string | null;
	channel_id: string | null;
	video_count: number;
	published_at: string | null;
	last_synced_at: string | null;
	created_at: string;
	updated_at: string;
}

export interface VideoStats {
	total_videos: number;
	categorized: number;
	uncategorized: number;
	categorization_percentage: number;
	top_categories: Array<{ name: string; count: number }>;
	top_tags: Array<{ name: string; count: number }>;
}

export interface SyncResponse {
	status: string;
	videos_synced: number;
	videos_categorized: number;
	total_videos: number;
}

export interface TagCloudItem {
	id: number;
	name: string;
	slug: string;
	usage_count: number;
	weight: number;
}

export interface PaginatedVideosResponse {
	items: Video[];
	total: number;
	page: number;
	page_size: number;
	total_pages: number;
}
