"use client";

import {
	BreadcrumbItem,
	Breadcrumbs,
	Button,
	Card,
	CardBody,
	Modal,
	ModalBody,
	ModalContent,
	ModalHeader,
	Spinner,
} from "@heroui/react";
import Image from "next/image";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useInView } from "react-intersection-observer";
import { playlistsApi, videosApi } from "@/api/api";
import FilterPanel from "@/components/FilterPanel";
import Navbar from "@/components/Navbar";
import VideoCard from "@/components/VideoCard";
import { useAuthGuard } from "@/hooks";
import type { CursorPaginatedVideosResponse, Playlist, Video } from "@/types";

export default function PlaylistDetailPage() {
	const router = useRouter();
	const params = useParams();
	const playlistId = parseInt(params.id as string, 10);
	const { isReady, isAuthenticated } = useAuthGuard();

	const [playlist, setPlaylist] = useState<Playlist | null>(null);
	// Ref so fetchPlaylistDetails can read playlist in the append-case without
	// adding it to useCallback deps (which would cause an infinite re-fetch loop).
	const playlistRef = useRef<Playlist | null>(null);
	const [videos, setVideos] = useState<Video[]>([]);
	const [loading, setLoading] = useState(true);
	const [loadingMore, setLoadingMore] = useState(false);
	const [syncing, setSyncing] = useState(false);
	const [categorizingId, setCategorizingId] = useState<number | null>(null);

	// Cursor-based pagination state
	const [nextCursor, setNextCursor] = useState<string | null>(null);
	const [hasMore, setHasMore] = useState(false);
	const [totalCount, setTotalCount] = useState(0);

	// Filter states
	const [selectedCategories, setSelectedCategories] = useState<number[]>([]);
	const [selectedTags, setSelectedTags] = useState<number[]>([]);
	const [searchQuery, setSearchQuery] = useState("");
	const [showOnlyCategorized, setShowOnlyCategorized] = useState<
		boolean | null
	>(null);

	const fetchPlaylistDetails = useCallback(
		async (cursor?: string | null, append = false) => {
			if (append) {
				setLoadingMore(true);
			} else {
				setLoading(true);
			}

			try {
				// Fetch playlist info only on initial load; use ref for append case
				// to avoid adding `playlist` state to deps (causes infinite loop).
				const playlistPromise = append
					? Promise.resolve({ data: playlistRef.current })
					: playlistsApi.getPlaylist(playlistId);

				const videosPromise = playlistsApi.getPlaylistVideos(playlistId, {
					cursor: cursor || undefined,
					limit: 20,
					category_ids:
						selectedCategories.length > 0
							? selectedCategories.join(",")
							: undefined,
					tag_ids: selectedTags.length > 0 ? selectedTags.join(",") : undefined,
					search: searchQuery || undefined,
				});

				const [playlistRes, videosRes] = await Promise.all([
					playlistPromise,
					videosPromise,
				]);

				if (!append) {
					playlistRef.current = playlistRes.data;
					setPlaylist(playlistRes.data);
				}

				const response = videosRes.data as CursorPaginatedVideosResponse;

				if (append) {
					setVideos((prev) => [...prev, ...response.videos]);
				} else {
					setVideos(response.videos);
				}

				setNextCursor(response.next_cursor);
				setHasMore(response.has_more);
				setTotalCount(response.total_count);
			} catch {
				// Failed to fetch playlist details - UI will show empty state
			} finally {
				setLoading(false);
				setLoadingMore(false);
			}
		},
		[playlistId, selectedCategories, selectedTags, searchQuery],
	);

	useEffect(() => {
		if (!isReady || !isAuthenticated) return;
		fetchPlaylistDetails();
	}, [isReady, isAuthenticated, fetchPlaylistDetails]);

	const { ref: sentinelRef, inView } = useInView({ rootMargin: "200px" });

	useEffect(() => {
		if (inView && hasMore && nextCursor && !loadingMore) {
			fetchPlaylistDetails(nextCursor, true);
		}
	}, [inView, hasMore, nextCursor, loadingMore, fetchPlaylistDetails]);

	const handleSyncVideos = async () => {
		setSyncing(true);
		try {
			await playlistsApi.syncPlaylistVideos(playlistId, {
				max_results: 50,
				auto_categorize: true,
			});
			await fetchPlaylistDetails();
		} catch {
			alert("Failed to sync playlist videos. Please try again.");
		} finally {
			setSyncing(false);
		}
	};

	const handleCategorize = async (videoId: number) => {
		setCategorizingId(videoId);
		try {
			await videosApi.categorizeVideo(videoId);
			await fetchPlaylistDetails();
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

	// Don't render anything until hydrated and authenticated
	if (!isReady || !isAuthenticated) {
		return (
			<div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
				<Spinner size="lg" />
			</div>
		);
	}

	return (
		<div className="min-h-screen bg-gray-50 dark:bg-gray-900">
			<Navbar />
			<div className="container mx-auto px-4 py-8 max-w-7xl">
				<div className="space-y-6">
					{/* Breadcrumbs */}
					<Breadcrumbs>
						<BreadcrumbItem onPress={() => router.push("/dashboard")}>
							Dashboard
						</BreadcrumbItem>
						<BreadcrumbItem onPress={() => router.push("/playlists")}>
							Playlists
						</BreadcrumbItem>
						<BreadcrumbItem>{playlist?.title || "Loading..."}</BreadcrumbItem>
					</Breadcrumbs>

					{/* Header */}
					{playlist && (
						<Card>
							<CardBody className="flex flex-row items-start gap-4">
								<Image
									src={playlist.thumbnail_url || "/placeholder-thumbnail.jpg"}
									alt={playlist.title}
									width={128}
									height={96}
									className="w-32 h-24 object-cover rounded"
								/>
								<div className="flex-1">
									<h1 className="text-2xl font-bold">{playlist.title}</h1>
									{playlist.description && (
										<p className="text-gray-600 dark:text-gray-400 mt-2 line-clamp-2">
											{playlist.description}
										</p>
									)}
									<div className="flex gap-4 mt-3 text-sm text-gray-500">
										<span>
											{totalCount > 0 ? totalCount : playlist.video_count}{" "}
											videos
										</span>
										{playlist.channel_title && <span>•</span>}
										{playlist.channel_title && (
											<span>{playlist.channel_title}</span>
										)}
									</div>
								</div>
								<Button color="primary" onPress={handleSyncVideos}>
									Sync Videos
								</Button>
							</CardBody>
						</Card>
					)}

					{/* Sync Modal */}
					<Modal
						isOpen={syncing}
						isDismissable={false}
						isKeyboardDismissDisabled={true}
						hideCloseButton={true}
						size="md"
						backdrop="blur"
					>
						<ModalContent>
							<ModalHeader className="flex flex-col gap-1">
								Syncing Playlist Videos
							</ModalHeader>
							<ModalBody className="py-8">
								<div className="flex flex-col items-center gap-4">
									<Spinner size="lg" color="primary" />
									<div className="text-center space-y-2">
										<p className="text-lg font-semibold">Please wait...</p>
										<p className="text-sm text-gray-600 dark:text-gray-400">
											Fetching videos from this playlist and categorizing them
											with AI.
										</p>
										<p className="text-sm text-gray-600 dark:text-gray-400">
											This may take a few minutes depending on the number of
											videos.
										</p>
									</div>
								</div>
							</ModalBody>
						</ModalContent>
					</Modal>

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
								<div className="space-y-6">
									<div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
										{videos.map((video) => (
											<VideoCard
												key={video.id}
												video={video}
												onCategorize={handleCategorize}
												isCategorizing={categorizingId === video.id}
											/>
										))}
									</div>

									{/* Infinite scroll sentinel */}
									<div ref={sentinelRef} className="h-1" />

									{/* Loading indicator */}
									{loadingMore && (
										<div className="flex justify-center pt-4">
											<Spinner size="md" />
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
										Try adjusting your filters or sync the playlist
									</p>
								</div>
							)}
						</div>
					</div>
				</div>
			</div>
		</div>
	);
}
