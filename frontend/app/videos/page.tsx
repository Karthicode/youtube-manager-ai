"use client";

import {
	Button,
	ButtonGroup,
	Pagination,
	Select,
	SelectItem,
	Spinner,
} from "@heroui/react";
import GridViewIcon from "@mui/icons-material/GridView";
import ViewListIcon from "@mui/icons-material/ViewList";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { videosApi, playlistsApi } from "@/api/api";
import FilterPanel from "@/components/FilterPanel";
import Navbar from "@/components/Navbar";
import VideoCard from "@/components/VideoCard";
import CreatePlaylistDialog from "@/components/CreatePlaylistDialog";
import { useAuthStore } from "@/store/auth";
import type { PaginatedVideosResponse, Video } from "@/types";

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
	const { isAuthenticated } = useAuthStore();

	const [videos, setVideos] = useState<Video[]>([]);
	const [loading, setLoading] = useState(true);
	const [categorizingId, setCategorizingId] = useState<number | null>(null);
	const [mounted, setMounted] = useState(false);

	// Filter states
	const [selectedCategories, setSelectedCategories] = useState<number[]>([]);
	const [selectedTags, setSelectedTags] = useState<number[]>([]);
	const [searchQuery, setSearchQuery] = useState("");
	const [debouncedSearchQuery, setDebouncedSearchQuery] = useState("");
	const [showOnlyCategorized, setShowOnlyCategorized] = useState<
		boolean | null
	>(null);

	// Pagination and sorting
	const [currentPage, setCurrentPage] = useState(1);
	const [totalPages, setTotalPages] = useState(1);
	const [totalVideos, setTotalVideos] = useState(0);
	const [sortBy, setSortBy] = useState("liked_at");
	const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
	const [pageSize, setPageSize] = useState(25);

	// View mode
	const [viewMode, setViewMode] = useState<"grid" | "list">("grid");

	// Create playlist dialog
	const [showCreatePlaylistDialog, setShowCreatePlaylistDialog] =
		useState(false);
	const [isCreatingPlaylist, setIsCreatingPlaylist] = useState(false);

	// Handle hydration
	useEffect(() => {
		setMounted(true);
	}, []);

	// Debounce search query
	useEffect(() => {
		const timer = setTimeout(() => {
			setDebouncedSearchQuery(searchQuery);
		}, 500);

		return () => clearTimeout(timer);
	}, [searchQuery]);

	const fetchVideos = useCallback(async () => {
		setLoading(true);
		try {
			const params: {
				page: number;
				page_size: number;
				sort_by: string;
				sort_order: string;
				category_ids?: string;
				tag_ids?: string;
				search?: string;
				is_categorized?: boolean;
			} = {
				page: currentPage,
				page_size: pageSize,
				sort_by: sortBy,
				sort_order: sortOrder,
			};

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

			const response = await videosApi.getLikedVideos(params);
			const paginatedData: PaginatedVideosResponse = response.data;

			setVideos(paginatedData.items);
			setTotalPages(paginatedData.total_pages);
			setTotalVideos(paginatedData.total);
		} catch (error) {
			console.error("Failed to fetch videos:", error);
		} finally {
			setLoading(false);
		}
	}, [
		currentPage,
		pageSize,
		sortBy,
		sortOrder,
		selectedCategories,
		selectedTags,
		debouncedSearchQuery,
		showOnlyCategorized,
	]);

	useEffect(() => {
		// Wait for Zustand to hydrate from localStorage
		if (!mounted) return;

		if (!isAuthenticated) {
			router.push("/");
			return;
		}

		// Read initial filters from URL
		const categorized = searchParams.get("categorized");
		if (categorized === "false") {
			setShowOnlyCategorized(false);
		}

		fetchVideos();
	}, [mounted, isAuthenticated, router, searchParams, fetchVideos]);

	const handleCategorize = async (videoId: number) => {
		setCategorizingId(videoId);
		try {
			await videosApi.categorizeVideo(videoId);
			await fetchVideos(); // Refresh the list
		} catch (error) {
			console.error("Failed to categorize video:", error);
		} finally {
			setCategorizingId(null);
		}
	};

	const handleClearFilters = () => {
		setSelectedCategories([]);
		setSelectedTags([]);
		setSearchQuery("");
		setShowOnlyCategorized(null);
		setCurrentPage(1);
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
		} catch (error) {
			console.error("Failed to create playlist:", error);
			alert("Failed to create playlist. Please try again.");
		} finally {
			setIsCreatingPlaylist(false);
		}
	};

	// Check if any filters are active
	const hasActiveFilters =
		selectedCategories.length > 0 ||
		selectedTags.length > 0 ||
		debouncedSearchQuery !== "" ||
		showOnlyCategorized !== null;

	// Don't render anything until hydrated
	if (!mounted) {
		return (
			<div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex justify-center items-center">
				<Spinner size="lg" />
			</div>
		);
	}

	if (!isAuthenticated) {
		return null;
	}

	return (
		<div className="min-h-screen bg-gray-50 dark:bg-gray-900">
			<Navbar />
			<div className="container mx-auto px-4 py-8 max-w-7xl">
				<div className="space-y-6">
					{/* Header */}
					<div className="flex flex-col sm:flex-row justify-between items-start sm:items-end gap-4">
						<div>
							<h1 className="text-3xl font-bold text-gray-900 dark:text-white">
								Liked Videos
							</h1>
							<p className="text-gray-600 dark:text-gray-400 mt-2">
								{totalVideos > 0 && (
									<>
										Showing {(currentPage - 1) * pageSize + 1} -{" "}
										{Math.min(currentPage * pageSize, totalVideos)} of{" "}
										{totalVideos} videos
									</>
								)}
							</p>
						</div>

						<div className="flex gap-3 items-end flex-wrap">
							{/* Create Playlist Button */}
							{hasActiveFilters && totalVideos > 0 && (
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
									Per page
								</span>
								<Select
									selectedKeys={[String(pageSize)]}
									onSelectionChange={(keys) => {
										const selected = Array.from(keys)[0];
										if (selected) {
											setPageSize(Number(selected));
											setCurrentPage(1);
										}
									}}
									className="w-24"
									size="md"
									variant="bordered"
									aria-label="Items per page"
								>
									<SelectItem key="25">25</SelectItem>
									<SelectItem key="50">50</SelectItem>
									<SelectItem key="100">100</SelectItem>
								</Select>
							</div>

							{/* Sort By */}
							<div className="flex flex-col gap-1">
								<label className="text-sm text-gray-600 dark:text-gray-400" htmlFor="sort-by">
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
					</div>

					{/* Content Grid */}
					<div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
						{/* Filters Sidebar */}
						<div className="lg:col-span-1">
							<FilterPanel
								selectedCategories={selectedCategories}
								selectedTags={selectedTags}
								searchQuery={searchQuery}
								showOnlyCategorized={showOnlyCategorized}
								onCategoriesChange={setSelectedCategories}
								onTagsChange={setSelectedTags}
								onSearchChange={setSearchQuery}
								onCategorizationFilterChange={setShowOnlyCategorized}
								onClearFilters={handleClearFilters}
							/>
						</div>

						{/* Videos Grid */}
						<div className="lg:col-span-3">
							{loading ? (
								<div className="flex justify-center items-center h-64">
									<Spinner size="lg" />
								</div>
							) : videos.length > 0 ? (
								<>
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
												isCategorizing={categorizingId === video.id}
												viewMode={viewMode}
											/>
										))}
									</div>

									{/* Pagination */}
									{totalPages > 1 && (
										<div className="flex justify-center mt-8">
											<Pagination
												total={totalPages}
												page={currentPage}
												onChange={setCurrentPage}
												showControls
												color="primary"
												size="lg"
												variant="bordered"
												radius="full"
												classNames={{
													cursor: "bg-primary text-white",
												}}
											/>
										</div>
									)}
								</>
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
