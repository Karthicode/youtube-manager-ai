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
	liked_videos: number;
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

export interface CursorPaginatedVideosResponse {
	videos: Video[];
	next_cursor: string | null;
	has_more: boolean;
	total_count: number;
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

export interface ChannelRecommendation {
	channel_id: string;
	channel_title: string;
	thumbnail_url: string | null;
	subscriber_count: number | null;
	video_count: number | null;
	description: string | null;
	recommendation_reason: string;
	score: number; // 0.0 to 1.0
	source: "content_based" | "youtube_api" | "hybrid";
}

export interface RecommendationsResponse {
	recommendations: ChannelRecommendation[];
	total_analyzed_channels: number;
	top_categories: string[];
	top_tags: string[];
}

// Delete by tags types
export interface DeleteFailure {
	video_id: number;
	youtube_id: string;
	title: string;
	error: string;
}

export interface DeleteProgressData {
	status: "running" | "completed" | "error" | "cancelled";
	total: number;
	unliked: number;
	deleted: number;
	failed: number;
	current_video: string | null;
	error?: string;
	failures: DeleteFailure[];
}

// Semantic search types
export interface SemanticSearchResult {
	id: number;
	youtube_id: string;
	title: string;
	description: string | null;
	thumbnail_url: string | null;
	channel_title: string | null;
	channel_id: string | null;
	duration_seconds: number | null;
	published_at: string | null;
	view_count: number | null;
	like_count: number | null;
	is_categorized: boolean;
	categorized_at: string | null;
	liked_at: string | null;
	created_at: string | null;
	user_id: number;
	similarity: number;
	categories: Category[];
	tags: Tag[];
}

export interface SemanticSearchResponse {
	query: string;
	results: SemanticSearchResult[];
	total_results: number;
}

export interface EmbeddingStats {
	total: number;
	embedded: number;
	not_embedded: number;
	percentage_embedded: number;
}

export interface EmbeddingGenerateResponse {
	success_count: number;
	failed_count: number;
	total: number;
	skipped: number;
	message: string;
}

// Smart Playlist types
export interface PlaylistVideoSelection {
	video_id: number;
	reason: string;
	order_position: number;
}

export interface PlaylistSuggestion {
	suggestion_id: string;
	title: string;
	description: string;
	videos: PlaylistVideoSelection[];
	watching_order_rationale: string;
	theme_summary: string;
}

export interface SmartPlaylistConfirmResponse {
	playlist: Playlist;
	total_videos: number;
	added_immediately: number;
	queued_for_background: number;
	job_id: string | null;
}

// Chat types
export interface ChatMessage {
	id?: number;
	role: "user" | "assistant";
	content: string;
	toolCalls?: ChatToolCall[];
	toolResults?: ChatToolResult[];
	videos?: Video[];
	created_at?: string;
}

export interface ChatToolCall {
	tool: string;
	arguments: Record<string, unknown>;
}

export interface ChatToolResult {
	tool: string;
	result: unknown;
}

export interface ChatSession {
	session_id: string;
	title?: string | null;
	created_at: string;
	last_message_at: string;
	message_count: number;
}

// Taste Profile types
export interface InterestCluster {
	label: string;
	percentage: number;
	representative_video_ids: number[];
	description: string;
}

export interface DriftEvent {
	period: string;
	from_interest: string;
	to_interest: string;
	magnitude: number;
	evidence_video_ids: number[];
}

export interface ConsumptionStyle {
	avg_duration_preference: string;
	channel_diversity: string;
	content_depth: string;
	viewing_pattern: string;
}

export interface TasteProfile {
	identity_summary: string;
	primary_interests: InterestCluster[];
	emerging_interests: InterestCluster[];
	declining_interests: InterestCluster[];
	consumption_style: ConsumptionStyle;
	drift_events: DriftEvent[];
	personality_tags: string[];
}

export interface TasteProfileResponse {
	profile: TasteProfile | null;
	status: "ready" | "generating" | "not_available";
	video_count: number;
	min_videos_required: number;
}
