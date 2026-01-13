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

// Insights types
export interface CategoryDistribution {
	name: string;
	count: number;
	percentage: number;
	color: string | null;
}

export interface TagDistribution {
	name: string;
	count: number;
	weight: number; // 1-5 scale for tag cloud sizing
}

export interface ChannelStats {
	channel_title: string;
	channel_id: string;
	video_count: number;
	total_views: number;
	avg_duration_seconds: number;
}

export interface TemporalData {
	label: string;
	count: number;
}

export interface DurationBucket {
	label: string;
	range_label: string;
	count: number;
	percentage: number;
	total_seconds: number;
}

export interface InsightsOverview {
	total_videos: number;
	categorized: number;
	uncategorized: number;
	unique_channels: number;
	unique_categories: number;
	unique_tags: number;
	total_watch_time_seconds: number;
	avg_video_duration_seconds: number;
	earliest_liked_at: string | null;
	latest_liked_at: string | null;
}

export interface ContentDistributionResponse {
	categories: CategoryDistribution[];
	tags: TagDistribution[];
}

export interface ChannelsResponse {
	top_channels: ChannelStats[];
	total_channels: number;
	channel_diversity_score: number;
}

export interface TemporalResponse {
	likes_by_month: TemporalData[];
	likes_by_day_of_week: TemporalData[];
	likes_by_hour: TemporalData[];
	published_by_year: TemporalData[];
}

export interface DurationResponse {
	buckets: DurationBucket[];
	avg_duration_seconds: number;
	total_watch_time_seconds: number;
}
