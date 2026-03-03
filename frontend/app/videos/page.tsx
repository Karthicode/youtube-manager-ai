"use client";

import {
	Button,
	ButtonGroup,
	Card,
	CardBody,
	Chip,
	Input,
	Progress,
	Select,
	SelectItem,
	Spinner,
	Switch,
	Tab,
	Tabs,
	Tooltip,
} from "@heroui/react";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import FavoriteIcon from "@mui/icons-material/Favorite";
import GridViewIcon from "@mui/icons-material/GridView";
import SearchIcon from "@mui/icons-material/Search";
import SyncIcon from "@mui/icons-material/Sync";
import ViewListIcon from "@mui/icons-material/ViewList";
import WatchLaterIcon from "@mui/icons-material/WatchLater";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { categoriesApi, playlistsApi, videosApi } from "@/api/api";
import CreatePlaylistDialog from "@/components/CreatePlaylistDialog";
import DeleteProgressSSE from "@/components/DeleteProgressSSE";
import DeleteVideosDialog from "@/components/DeleteVideosDialog";
import FilterPanel from "@/components/FilterPanel";
import Navbar from "@/components/Navbar";
import VideoCard from "@/components/VideoCard";
import { useAuthGuard } from "@/hooks";
import { useMiniPlayerStore } from "@/store/miniPlayer";
import type {
	CursorPaginatedVideosResponse,
	EmbeddingStats,
	SemanticSearchResult,
	Video,
} from "@/types";

const SORT_OPTIONS = [
	{ value: "liked_at", label: "Liked Date" },
	{ value: "published_at", label: "Published Date" },
	{ value: "title", label: "Title" },
	{ value: "view_count", label: "Views" },
	{ value: "duration_seconds", label: "Duration" },
];

function VideosPageContent() {
	const router = useRouter();
	const searchParams = useSearchParams();
	const { isReady, isAuthenticated } = useAuthGuard();
	const {
		openPlayer,
		currentVideo: currentMiniVideo,
		isOpen: isMiniOpen,
	} = useMiniPlayerStore();

	const [videos, setVideos] = useState<Video[]>([]);
	const [loading, setLoading] = useState(true);
	const [loadingMore, setLoadingMore] = useState(false);
	const [categorizingId, setCategorizingId] = useState<number | null>(null);

	// Tab state - "liked" or "watch_later"
	const [activeTab, setActiveTab] = useState<"liked" | "watch_later">("liked");
	const [syncingWatchLater, setSyncingWatchLater] = useState(false);

	// Filter states
	const [selectedCategories, setSelectedCategories] = useState<number[]>([]);
	const [selectedTags, setSelectedTags] = useState<number[]>([]);
	const [searchQuery, setSearchQuery] = useState("");
	const [debouncedSearchQuery, setDebouncedSearchQuery] = useState("");
	const [showOnlyCategorized, setShowOnlyCategorized] = useState<
		boolean | null
	>(null);

	// Cursor-based pagination state
	const [nextCursor, setNextCursor] = useState<string | null>(null);
	const [hasMore, setHasMore] = useState(false);
	const [totalVideos, setTotalVideos] = useState(0);

	// Sorting
	const [sortBy, setSortBy] = useState("liked_at");
	const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
	const [pageSize, setPageSize] = useState(25);

	// View mode
	const [viewMode, setViewMode] = useState<"grid" | "list">("grid");

	// Create playlist dialog
	const [showCreatePlaylistDialog, setShowCreatePlaylistDialog] =
		useState(false);
	const [isCreatingPlaylist, setIsCreatingPlaylist] = useState(false);

	// Delete by tags state
	const [showDeleteDialog, setShowDeleteDialog] = useState(false);
	const [deleteJobId, setDeleteJobId] = useState<string | null>(null);
	const [videosToDeleteCount, setVideosToDeleteCount] = useState(0);
	const [deleteTagNames, setDeleteTagNames] = useState<string[]>([]);
	const [isStartingDelete, setIsStartingDelete] = useState(false);

	// Semantic search state
	const [semanticSearchEnabled, setSemanticSearchEnabled] = useState(false);
	const [semanticQuery, setSemanticQuery] = useState("");
	const [semanticResults, setSemanticResults] = useState<
		SemanticSearchResult[]
	>([]);
	const [semanticLoading, setSemanticLoading] = useState(false);
	const [embeddingStats, setEmbeddingStats] = useState<EmbeddingStats | null>(
		null,
	);
	const [isGeneratingEmbeddings, setIsGeneratingEmbeddings] = useState(false);

	// Debounce search query
	useEffect(() => {
		const timer = setTimeout(() => {
			setDebouncedSearchQuery(searchQuery);
		}, 500);

		return () => clearTimeout(timer);
	}, [searchQuery]);

	// Fetch embedding stats when semantic search is enabled
	const fetchEmbeddingStats = useCallback(async () => {
		try {
			const response = await videosApi.getEmbeddingStats();
			setEmbeddingStats(response.data);
		} catch {
			// Failed to fetch embedding stats
		}
	}, []);

	// Semantic search function
	const performSemanticSearch = useCallback(async (query: string) => {
		if (!query.trim()) {
			setSemanticResults([]);
			return;
		}

		setSemanticLoading(true);
		try {
			const response = await videosApi.semanticSearch({
				q: query,
				limit: 50,
				similarity_threshold: 0.25,
			});
			setSemanticResults(response.data.results);
		} catch {
			setSemanticResults([]);
		} finally {
			setSemanticLoading(false);
		}
	}, []);

	// Debounced semantic search
	useEffect(() => {
		if (!semanticSearchEnabled) return;

		const timer = setTimeout(() => {
			performSemanticSearch(semanticQuery);
		}, 500);

		return () => clearTimeout(timer);
	}, [semanticQuery, semanticSearchEnabled, performSemanticSearch]);

	// Embedding progress state
	const [embeddingProgress, setEmbeddingProgress] = useState<{
		total: number;
		completed: number;
		failed: number;
		currentVideo: string | null;
		lastError: string | null;
	} | null>(null);

	const activePlaybackQueue = useMemo(() => {
		const sourceVideos = semanticSearchEnabled ? semanticResults : videos;

		return sourceVideos
			.filter((video) => Boolean(video.youtube_id))
			.map((video) => ({
				id: video.id,
				youtubeId: video.youtube_id,
				title: video.title,
				channelTitle: video.channel_title,
				thumbnailUrl: video.thumbnail_url,
			}));
	}, [semanticSearchEnabled, semanticResults, videos]);

	// Generate embeddings with SSE progress (inline streaming)
	const handleGenerateEmbeddings = async (forceRegenerate = false) => {
		setIsGeneratingEmbeddings(true);
		setEmbeddingProgress(null);

		try {
			const token = localStorage.getItem("access_token");
			const apiUrl =
				process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

			// Connect directly to the inline SSE endpoint
			const params = new URLSearchParams({
				token: token || "",
				max_concurrent: "5",
				force_regenerate: forceRegenerate.toString(),
			});

			const eventSource = new EventSource(
				`${apiUrl}/videos/embeddings/generate/stream?${params.toString()}`,
			);

			eventSource.onmessage = (event) => {
				const data = JSON.parse(event.data);
				setEmbeddingProgress({
					total: data.total,
					completed: data.completed,
					failed: data.failed,
					currentVideo: data.current_video,
					lastError: data.last_error || null,
				});

				if (data.status === "completed" || data.status === "error") {
					eventSource.close();
					setIsGeneratingEmbeddings(false);
					fetchEmbeddingStats();

					if (data.status === "completed") {
						setTimeout(() => setEmbeddingProgress(null), 3000);
					} else if (data.error) {
						alert(`Embedding failed: ${data.error}`);
					}
				}
			};

			eventSource.onerror = () => {
				eventSource.close();
				setIsGeneratingEmbeddings(false);
				fetchEmbeddingStats();
			};
		} catch {
			alert("Failed to start embedding generation. Please try again.");
			setIsGeneratingEmbeddings(false);
		}
	};

	// Fetch embedding stats when semantic search is toggled on
	useEffect(() => {
		if (semanticSearchEnabled) {
			fetchEmbeddingStats();
		}
	}, [semanticSearchEnabled, fetchEmbeddingStats]);

	const fetchVideos = useCallback(
		async (cursor?: string | null, append = false) => {
			if (append) {
				setLoadingMore(true);
			} else {
				setLoading(true);
			}

			try {
				const params: {
					cursor?: string;
					limit: number;
					sort_by: string;
					sort_order: string;
					category_ids?: string;
					tag_ids?: string;
					search?: string;
					is_categorized?: boolean;
				} = {
					limit: pageSize,
					sort_by: sortBy,
					sort_order: sortOrder,
				};

				if (cursor) {
					params.cursor = cursor;
				}

				if (selectedCategories.length > 0) {
					params.category_ids = selectedCategories.join(",");
				}

				if (selectedTags.length > 0) {
					params.tag_ids = selectedTags.join(",");
				}

				if (debouncedSearchQuery) {
					params.search = debouncedSearchQuery;
				}

				if (showOnlyCategorized !== null) {
					params.is_categorized = showOnlyCategorized;
				}

				// Use the correct API based on active tab
				const response =
					activeTab === "liked"
						? await videosApi.getLikedVideos(params)
						: await videosApi.getWatchLaterVideos(params);
				const data: CursorPaginatedVideosResponse = response.data;

				if (append) {
					setVideos((prev) => [...prev, ...data.videos]);
				} else {
					setVideos(data.videos);
				}

				setNextCursor(data.next_cursor);
				setHasMore(data.has_more);
				setTotalVideos(data.total_count);
			} catch {
				// Failed to fetch videos - UI will show empty state
			} finally {
				setLoading(false);
				setLoadingMore(false);
			}
		},
		[
			pageSize,
			sortBy,
			sortOrder,
			selectedCategories,
			selectedTags,
			debouncedSearchQuery,
			showOnlyCategorized,
			activeTab,
		],
	);

	// Initialize filters from URL on mount
	useEffect(() => {
		if (!isReady) return;

		const categorized = searchParams.get("categorized");
		if (categorized === "false") {
			setShowOnlyCategorized(false);
		}

		// If a category name is provided in the URL, map it to an id and select it
		const categoryParam = searchParams.get("category");
		if (categoryParam) {
			(async () => {
				try {
					const res = await categoriesApi.getCategories();
					const match = res.data.find(
						(c: { id: number; name: string }) =>
							c.name.toLowerCase() === categoryParam.toLowerCase(),
					);
					if (match) {
						setSelectedCategories([match.id]);
					}
				} catch {
					// Failed to map category from URL - ignore
				}
			})();
		}
	}, [isReady, searchParams]);

	// Fetch videos when filters or authentication changes
	useEffect(() => {
		if (!isReady || !isAuthenticated) return;
		fetchVideos();
	}, [isReady, isAuthenticated, fetchVideos]);

	const handleLoadMore = () => {
		if (hasMore && nextCursor && !loadingMore) {
			fetchVideos(nextCursor, true);
		}
	};

	const handleCategorize = async (videoId: number) => {
		setCategorizingId(videoId);
		try {
			await videosApi.categorizeVideo(videoId);
			await fetchVideos(); // Refresh the list
		} catch {
			// Failed to categorize video - user can retry
		} finally {
			setCategorizingId(null);
		}
	};

	const handleClearFilters = () => {
		setSelectedCategories([]);
		setSelectedTags([]);
		setSearchQuery("");
		setShowOnlyCategorized(null);
	};

	const handleTabChange = (key: string | number) => {
		const newTab = key as "liked" | "watch_later";
		if (newTab !== activeTab) {
			setActiveTab(newTab);
			// Reset pagination state when switching tabs
			setNextCursor(null);
			setHasMore(false);
			setVideos([]);
		}
	};

	const handleSyncWatchLater = async () => {
		setSyncingWatchLater(true);
		try {
			await videosApi.syncWatchLaterVideos({ max_results: 20 });
			await fetchVideos();
		} catch {
			alert("Failed to sync Watch Later videos. Please try again.");
		} finally {
			setSyncingWatchLater(false);
		}
	};

	const handleCategorizationFilterChange = (value: boolean | null) => {
		setShowOnlyCategorized(value);
	};

	const handleCategoriesChange = (categories: number[]) => {
		setSelectedCategories(categories);
	};

	const handleTagsChange = (tags: number[]) => {
		setSelectedTags(tags);
	};

	const toggleSortOrder = () => {
		setSortOrder(sortOrder === "asc" ? "desc" : "asc");
	};

	const handleCreatePlaylist = async (
		title: string,
		description: string,
		privacyStatus: string,
	) => {
		setIsCreatingPlaylist(true);
		try {
			const response = await playlistsApi.createFromFilters({
				title,
				description,
				privacy_status: privacyStatus,
				filter_params: {
					category_ids:
						selectedCategories.length > 0 ? selectedCategories : undefined,
					tag_ids: selectedTags.length > 0 ? selectedTags : undefined,
					search: debouncedSearchQuery || undefined,
					is_categorized: showOnlyCategorized ?? undefined,
				},
			});

			// Success! Show message and navigate to playlists
			alert(
				`Playlist created! ${response.data.added_immediately} videos added immediately. ${response.data.queued_for_background > 0 ? `${response.data.queued_for_background} videos will be added in the background.` : ""}`,
			);

			// Close dialog
			setShowCreatePlaylistDialog(false);

			// Navigate to playlists page
			router.push("/playlists");
		} catch {
			alert("Failed to create playlist. Please try again.");
		} finally {
			setIsCreatingPlaylist(false);
		}
	};

	// Delete by tags handlers
	const handleDeleteByTags = async (tagIds: number[], tagNames: string[]) => {
		try {
			const response = await videosApi.getVideoCountByTags(tagIds);
			setVideosToDeleteCount(response.data.count);
			setDeleteTagNames(tagNames);
			setShowDeleteDialog(true);
		} catch {
			alert("Failed to count videos. Please try again.");
		}
	};

	const handleConfirmDelete = async () => {
		setIsStartingDelete(true);
		try {
			const response = await videosApi.startDeleteByTags(selectedTags);
			setDeleteJobId(response.data.job_id);
			setShowDeleteDialog(false);
		} catch {
			alert("Failed to start deletion. Please try again.");
		} finally {
			setIsStartingDelete(false);
		}
	};

	const handleDeleteComplete = () => {
		setDeleteJobId(null);
		handleClearFilters();
		fetchVideos();
	};

	const handleDeleteError = (error: string) => {
		alert(`Deletion failed: ${error}`);
		setDeleteJobId(null);
	};

	const handlePlayInMiniPlayer = useCallback(
		(video: Video) => {
			const queueIndex = activePlaybackQueue.findIndex(
				(item) => item.id === video.id,
			);
			if (queueIndex < 0) return;

			openPlayer(
				activePlaybackQueue[queueIndex],
				activePlaybackQueue,
				queueIndex,
				{
					type: "videos",
					sourceTab: activeTab,
					semanticSearch: semanticSearchEnabled,
					query:
						semanticSearchEnabled && semanticQuery.trim()
							? semanticQuery.trim()
							: null,
				},
			);
		},
		[
			activePlaybackQueue,
			activeTab,
			openPlayer,
			semanticQuery,
			semanticSearchEnabled,
		],
	);

	// Check if any filters are active
	const hasActiveFilters =
		selectedCategories.length > 0 ||
		selectedTags.length > 0 ||
		debouncedSearchQuery !== "" ||
		showOnlyCategorized !== null;

	// Don't render anything until hydrated and authenticated
	if (!isReady || !isAuthenticated) {
		return (
			<div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex justify-center items-center">
				<Spinner size="lg" />
			</div>
		);
	}

	return (
		<div className="min-h-screen bg-gray-50 dark:bg-gray-900">
			<Navbar />
			<div className="container mx-auto px-4 py-8 max-w-7xl">
				<div className="space-y-6">
					{/* Header with Tabs */}
					<div className="flex flex-col gap-4">
						<div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
							<h1 className="text-3xl font-bold text-gray-900 dark:text-white">
								Videos
							</h1>
							{/* Sync Watch Later Button - Only show when Watch Later tab is active */}
							{activeTab === "watch_later" && (
								<Button
									color="primary"
									variant="flat"
									onPress={handleSyncWatchLater}
									isLoading={syncingWatchLater}
									startContent={
										!syncingWatchLater && <SyncIcon fontSize="small" />
									}
								>
									Sync Watch Later
								</Button>
							)}
						</div>

						{/* Tabs */}
						<Tabs
							selectedKey={activeTab}
							onSelectionChange={handleTabChange}
							aria-label="Video source tabs"
							color="primary"
							variant="underlined"
							classNames={{
								tabList: "gap-6",
								cursor: "w-full",
								tab: "max-w-fit px-0 h-12",
							}}
						>
							<Tab
								key="liked"
								title={
									<div className="flex items-center gap-2">
										<FavoriteIcon fontSize="small" />
										<span>Liked Videos</span>
									</div>
								}
							/>
							<Tab
								key="watch_later"
								title={
									<div className="flex items-center gap-2">
										<WatchLaterIcon fontSize="small" />
										<span>Watch Later</span>
									</div>
								}
							/>
						</Tabs>

						<p className="text-gray-600 dark:text-gray-400">
							{semanticSearchEnabled ? (
								semanticResults.length > 0 ? (
									<>Found {semanticResults.length} similar videos</>
								) : semanticQuery ? (
									<>Searching...</>
								) : (
									<>Enter a query to search semantically</>
								)
							) : (
								totalVideos > 0 && (
									<>
										Showing {videos.length} of {totalVideos}{" "}
										{activeTab === "liked"
											? "liked videos"
											: "Watch Later videos"}
									</>
								)
							)}
						</p>
					</div>

					<div className="flex justify-end gap-3 items-end flex-wrap">
						{/* Semantic Search Toggle */}
						<div className="flex flex-col gap-1">
							<span className="text-sm text-gray-600 dark:text-gray-400">
								AI Search
							</span>
							<Tooltip
								content="Search by meaning, not just keywords"
								placement="bottom"
							>
								<div className="flex items-center gap-2 h-10 px-3 border rounded-lg border-gray-300 dark:border-gray-600">
									<AutoAwesomeIcon
										fontSize="small"
										className={
											semanticSearchEnabled ? "text-primary" : "text-gray-400"
										}
									/>
									<Switch
										size="sm"
										isSelected={semanticSearchEnabled}
										onValueChange={setSemanticSearchEnabled}
										aria-label="Enable semantic search"
									/>
								</div>
							</Tooltip>
						</div>

						{/* Create Playlist Button */}
						{!semanticSearchEnabled && hasActiveFilters && totalVideos > 0 && (
							<Button
								color="success"
								variant="shadow"
								onPress={() => setShowCreatePlaylistDialog(true)}
								className="h-10"
							>
								Create Playlist ({totalVideos})
							</Button>
						)}

						{/* View Toggle */}
						<div className="flex flex-col gap-1">
							<span className="text-sm text-gray-600 dark:text-gray-400">
								View
							</span>
							<ButtonGroup size="md" variant="bordered">
								<Button
									onPress={() => setViewMode("grid")}
									color={viewMode === "grid" ? "primary" : "default"}
									isIconOnly
								>
									<GridViewIcon fontSize="small" />
								</Button>
								<Button
									onPress={() => setViewMode("list")}
									color={viewMode === "list" ? "primary" : "default"}
									isIconOnly
								>
									<ViewListIcon fontSize="small" />
								</Button>
							</ButtonGroup>
						</div>

						{/* Per Page */}
						<div className="flex flex-col gap-1">
							<span className="text-sm text-gray-600 dark:text-gray-400">
								Per load
							</span>
							<Select
								selectedKeys={[String(pageSize)]}
								onSelectionChange={(keys) => {
									const selected = Array.from(keys)[0];
									if (selected) {
										setPageSize(Number(selected));
									}
								}}
								className="w-24"
								size="md"
								variant="bordered"
								aria-label="Items per load"
							>
								<SelectItem key="25">25</SelectItem>
								<SelectItem key="50">50</SelectItem>
								<SelectItem key="100">100</SelectItem>
							</Select>
						</div>

						{/* Sort By */}
						<div className="flex flex-col gap-1">
							<label
								className="text-sm text-gray-600 dark:text-gray-400"
								htmlFor="sort-by"
							>
								Sort by
							</label>
							<Select
								selectedKeys={[sortBy]}
								onSelectionChange={(keys) => {
									const selected = Array.from(keys)[0];
									if (selected) setSortBy(selected as string);
								}}
								className="w-48"
								size="md"
								variant="bordered"
								aria-label="Sort by"
							>
								{SORT_OPTIONS.map((option) => (
									<SelectItem key={option.value}>{option.label}</SelectItem>
								))}
							</Select>
						</div>

						{/* Sort Order */}
						<Button
							size="md"
							variant="bordered"
							onPress={toggleSortOrder}
							className="h-10 mt-6"
							color="primary"
						>
							{sortOrder === "asc" ? "↑ Asc" : "↓ Desc"}
						</Button>
					</div>

					{/* Content Grid */}
					<div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
						{/* Filters Sidebar / Semantic Search Panel */}
						<div className="lg:col-span-1">
							{semanticSearchEnabled ? (
								<Card className="w-full shadow-md">
									<CardBody className="gap-4">
										<div className="flex items-center gap-2">
											<AutoAwesomeIcon className="text-primary" />
											<h3 className="text-lg font-semibold">
												AI Semantic Search
											</h3>
										</div>
										<p className="text-sm text-gray-500 dark:text-gray-400">
											Search by meaning, not just keywords. Find videos even if
											they don&apos;t contain your exact words.
										</p>

										{/* Embedding Stats & Progress */}
										{embeddingStats && (
											<div className="space-y-2">
												{embeddingProgress ? (
													<>
														<div className="flex justify-between text-sm">
															<span className="text-gray-600 dark:text-gray-400">
																Indexing progress:
															</span>
															<span className="font-medium">
																{embeddingProgress.completed} /{" "}
																{embeddingProgress.total}
															</span>
														</div>
														<Progress
															value={
																(embeddingProgress.completed /
																	embeddingProgress.total) *
																100
															}
															color="primary"
															size="sm"
															className="max-w-full"
														/>
														{embeddingProgress.currentVideo && (
															<p className="text-xs text-gray-500 truncate">
																{embeddingProgress.currentVideo}
															</p>
														)}
														{embeddingProgress.failed > 0 && (
															<p className="text-xs text-danger">
																{embeddingProgress.failed} failed
															</p>
														)}
														{embeddingProgress.lastError && (
															<p className="text-xs text-danger mt-1 break-words">
																Error: {embeddingProgress.lastError}
															</p>
														)}
													</>
												) : (
													<>
														<div className="flex justify-between text-sm">
															<span className="text-gray-600 dark:text-gray-400">
																Videos indexed:
															</span>
															<span className="font-medium">
																{embeddingStats.embedded} /{" "}
																{embeddingStats.total}
															</span>
														</div>
														<Progress
															value={embeddingStats.percentage_embedded}
															color={
																embeddingStats.percentage_embedded === 100
																	? "success"
																	: "primary"
															}
															size="sm"
															className="max-w-full"
														/>
													</>
												)}
												{!embeddingProgress && (
													<div className="flex gap-2 mt-2">
														{embeddingStats.not_embedded > 0 && (
															<Button
																color="primary"
																variant="flat"
																size="sm"
																onPress={() => handleGenerateEmbeddings(false)}
																isLoading={isGeneratingEmbeddings}
																className="flex-1"
															>
																{isGeneratingEmbeddings
																	? "Starting..."
																	: `Index ${embeddingStats.not_embedded} Videos`}
															</Button>
														)}
														{embeddingStats.embedded > 0 && (
															<Tooltip content="Re-index all videos with fresh embeddings">
																<Button
																	color="secondary"
																	variant="flat"
																	size="sm"
																	onPress={() => handleGenerateEmbeddings(true)}
																	isLoading={isGeneratingEmbeddings}
																	isDisabled={isGeneratingEmbeddings}
																>
																	Regenerate All
																</Button>
															</Tooltip>
														)}
													</div>
												)}
											</div>
										)}

										{/* Search Input */}
										<Input
											type="text"
											placeholder="e.g., 'cooking tutorials' or 'learn python'"
											value={semanticQuery}
											onValueChange={setSemanticQuery}
											startContent={
												<SearchIcon
													fontSize="small"
													className="text-default-400"
												/>
											}
											isClearable
											onClear={() => setSemanticQuery("")}
											variant="bordered"
											size="lg"
											radius="lg"
											classNames={{
												input: "text-base",
											}}
										/>

										<p className="text-xs text-gray-400">
											Try describing what you&apos;re looking for in natural
											language
										</p>
									</CardBody>
								</Card>
							) : (
								<FilterPanel
									selectedCategories={selectedCategories}
									selectedTags={selectedTags}
									searchQuery={searchQuery}
									showOnlyCategorized={showOnlyCategorized}
									onCategoriesChange={handleCategoriesChange}
									onTagsChange={handleTagsChange}
									onSearchChange={setSearchQuery}
									onCategorizationFilterChange={
										handleCategorizationFilterChange
									}
									onClearFilters={handleClearFilters}
									onDeleteByTags={handleDeleteByTags}
								/>
							)}
						</div>

						{/* Videos Grid */}
						<div className="lg:col-span-3">
							{/* Delete Progress */}
							{deleteJobId && (
								<DeleteProgressSSE
									jobId={deleteJobId}
									onComplete={handleDeleteComplete}
									onError={handleDeleteError}
								/>
							)}

							{/* Semantic Search Results */}
							{semanticSearchEnabled ? (
								semanticLoading ? (
									<div className="flex justify-center items-center h-64">
										<Spinner size="lg" />
									</div>
								) : semanticResults.length > 0 ? (
									<div className="space-y-6">
										<div
											className={
												viewMode === "grid"
													? "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6"
													: "flex flex-col gap-4"
											}
										>
											{semanticResults.map((result) => (
												<div key={result.id} className="relative">
													<VideoCard
														video={result as unknown as Video}
														onCategorize={handleCategorize}
														onPlay={handlePlayInMiniPlayer}
														isCategorizing={categorizingId === result.id}
														isPlaying={
															isMiniOpen && currentMiniVideo?.id === result.id
														}
														viewMode={viewMode}
													/>
													{/* Similarity Score Badge */}
													<Chip
														color={
															result.similarity > 0.5
																? "success"
																: result.similarity > 0.35
																	? "primary"
																	: "warning"
														}
														variant="flat"
														size="sm"
														className="absolute top-2 right-2 z-10"
													>
														{Math.round(result.similarity * 100)}% match
													</Chip>
												</div>
											))}
										</div>
									</div>
								) : semanticQuery ? (
									<div className="text-center py-12">
										<p className="text-gray-500 text-lg">
											No similar videos found
										</p>
										<p className="text-gray-400 text-sm mt-2">
											Try a different search query
										</p>
									</div>
								) : (
									<div className="text-center py-12">
										<AutoAwesomeIcon
											className="text-gray-300 dark:text-gray-600 mb-4"
											style={{ fontSize: 64 }}
										/>
										<p className="text-gray-500 text-lg">
											Enter a search query to find similar videos
										</p>
										<p className="text-gray-400 text-sm mt-2">
											{embeddingStats && embeddingStats.embedded > 0
												? `${embeddingStats.embedded} videos are indexed and ready to search`
												: "Index your videos first to enable semantic search"}
										</p>
									</div>
								)
							) : loading ? (
								<div className="flex justify-center items-center h-64">
									<Spinner size="lg" />
								</div>
							) : videos.length > 0 ? (
								<div className="space-y-6">
									<div
										className={
											viewMode === "grid"
												? "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6"
												: "flex flex-col gap-4"
										}
									>
										{videos.map((video) => (
											<VideoCard
												key={video.id}
												video={video}
												onCategorize={handleCategorize}
												onPlay={handlePlayInMiniPlayer}
												isCategorizing={categorizingId === video.id}
												isPlaying={
													isMiniOpen && currentMiniVideo?.id === video.id
												}
												viewMode={viewMode}
											/>
										))}
									</div>

									{/* Load More Button */}
									{hasMore && (
										<div className="flex justify-center pt-4">
											<Button
												color="primary"
												variant="flat"
												onPress={handleLoadMore}
												isLoading={loadingMore}
												className="min-w-[200px]"
											>
												{loadingMore
													? "Loading..."
													: `Load More (${videos.length} of ${totalVideos})`}
											</Button>
										</div>
									)}

									{/* Showing count */}
									{!hasMore && videos.length > 0 && (
										<p className="text-center text-sm text-gray-500">
											Showing all {videos.length} videos
										</p>
									)}
								</div>
							) : (
								<div className="text-center py-12">
									<p className="text-gray-500 text-lg">No videos found</p>
									<p className="text-gray-400 text-sm mt-2">
										Try adjusting your filters or sync your videos
									</p>
								</div>
							)}
						</div>
					</div>
				</div>

				{/* Create Playlist Dialog */}
				<CreatePlaylistDialog
					isOpen={showCreatePlaylistDialog}
					onClose={() => setShowCreatePlaylistDialog(false)}
					onConfirm={handleCreatePlaylist}
					filterParams={{
						category_ids: selectedCategories,
						tag_ids: selectedTags,
						search: debouncedSearchQuery,
						is_categorized: showOnlyCategorized ?? undefined,
					}}
					videoCount={totalVideos}
					isCreating={isCreatingPlaylist}
				/>

				{/* Delete Videos Dialog */}
				<DeleteVideosDialog
					isOpen={showDeleteDialog}
					onClose={() => setShowDeleteDialog(false)}
					onConfirm={handleConfirmDelete}
					videoCount={videosToDeleteCount}
					tagNames={deleteTagNames}
					isDeleting={isStartingDelete}
				/>
			</div>
		</div>
	);
}

export default function VideosPage() {
	return (
		<Suspense
			fallback={
				<div className="min-h-screen bg-gray-50 dark:bg-gray-900">
					<div className="flex justify-center items-center h-screen">
						<Spinner size="lg" />
					</div>
				</div>
			}
		>
			<VideosPageContent />
		</Suspense>
	);
}
