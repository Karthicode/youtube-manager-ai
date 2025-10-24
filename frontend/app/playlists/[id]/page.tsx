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
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { playlistsApi, videosApi } from "@/api/api";
import FilterPanel from "@/components/FilterPanel";
import Navbar from "@/components/Navbar";
import VideoCard from "@/components/VideoCard";
import { useAuthStore } from "@/store/auth";
import type { Playlist, Video } from "@/types";

export default function PlaylistDetailPage() {
	const router = useRouter();
	const params = useParams();
	const playlistId = parseInt(params.id as string, 10);
	const { isAuthenticated } = useAuthStore();

	const [playlist, setPlaylist] = useState<Playlist | null>(null);
	const [videos, setVideos] = useState<Video[]>([]);
	const [loading, setLoading] = useState(true);
	const [syncing, setSyncing] = useState(false);
	const [categorizingId, setCategorizingId] = useState<number | null>(null);

	// Filter states
	const [selectedCategories, setSelectedCategories] = useState<number[]>([]);
	const [selectedTags, setSelectedTags] = useState<number[]>([]);
	const [searchQuery, setSearchQuery] = useState("");
	const [showOnlyCategorized, setShowOnlyCategorized] = useState<
		boolean | null
	>(null);

	const fetchPlaylistDetails = useCallback(async () => {
		setLoading(true);
		try {
			// Fetch playlist info and videos
			const [playlistRes, videosRes] = await Promise.all([
				playlistsApi.getPlaylist(playlistId),
				playlistsApi.getPlaylistVideos(playlistId, {
					category_ids:
						selectedCategories.length > 0
							? selectedCategories.join(",")
							: undefined,
					tag_ids: selectedTags.length > 0 ? selectedTags.join(",") : undefined,
					search: searchQuery || undefined,
				}),
			]);

			setPlaylist(playlistRes.data);
			setVideos(videosRes.data);
		} catch (error) {
			console.error("Failed to fetch playlist details:", error);
		} finally {
			setLoading(false);
		}
	}, [playlistId, selectedCategories, selectedTags, searchQuery]);

	useEffect(() => {
		if (!isAuthenticated) {
			router.push("/");
			return;
		}

		fetchPlaylistDetails();
	}, [isAuthenticated, router, fetchPlaylistDetails]);

	const handleSyncVideos = async () => {
		setSyncing(true);
		try {
			await playlistsApi.syncPlaylistVideos(playlistId, {
				max_results: 50,
				auto_categorize: true,
			});
			await fetchPlaylistDetails();
		} catch (error) {
			console.error("Failed to sync playlist videos:", error);
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
	};

	if (!isAuthenticated) {
		return null;
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
								<img
									src={playlist.thumbnail_url || "/placeholder-thumbnail.jpg"}
									alt={playlist.title}
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
										<span>{playlist.video_count} videos</span>
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
