"use client";

import {
	Button,
	Card,
	CardBody,
	CardFooter,
	Image,
	Spinner,
} from "@heroui/react";
import { formatDistanceToNow } from "date-fns";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { playlistsApi } from "@/api/api";
import Navbar from "@/components/Navbar";
import { useAuthStore } from "@/store/auth";
import type { Playlist } from "@/types";

export default function PlaylistsPage() {
	const router = useRouter();
	const { isAuthenticated, isHydrated } = useAuthStore();

	const [playlists, setPlaylists] = useState<Playlist[]>([]);
	const [loading, setLoading] = useState(true);
	const [syncing, setSyncing] = useState(false);

	const fetchPlaylists = useCallback(async () => {
		setLoading(true);
		try {
			const response = await playlistsApi.getPlaylists({ page_size: 50 });
			setPlaylists(response.data);
		} catch (error) {
			console.error("Failed to fetch playlists:", error);
		} finally {
			setLoading(false);
		}
	}, []);

	const syncPlaylistsFromYouTube = useCallback(async () => {
		setSyncing(true);
		try {
			await playlistsApi.syncPlaylists({ max_results: 50 });
			await fetchPlaylists();
		} catch (error) {
			console.error("Failed to sync playlists:", error);
		} finally {
			setSyncing(false);
		}
	}, [fetchPlaylists]);

	useEffect(() => {
		if (!isAuthenticated) {
			router.push("/");
			return;
		}

		// Auto-sync playlists on page load
		syncPlaylistsFromYouTube();
	}, [isAuthenticated, router, syncPlaylistsFromYouTube]);

	const handleViewPlaylist = (playlistId: number) => {
		router.push(`/playlists/${playlistId}`);
	};

	// Show loading spinner until hydration is complete
	if (!isHydrated) {
		return (
			<div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
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
					<div className="flex justify-between items-center">
						<div>
							<h1 className="text-3xl font-bold">Playlists</h1>
							<p className="text-gray-600 dark:text-gray-400 mt-1">
								{syncing
									? "Syncing with YouTube..."
									: playlists.length > 0
										? `${playlists.length} playlists`
										: "No playlists found"}
							</p>
						</div>
					</div>

					{/* Content */}
					{syncing ? (
						<div className="flex flex-col justify-center items-center h-64 gap-4">
							<Spinner size="lg" color="primary" />
							<div className="text-center space-y-2">
								<p className="text-lg font-semibold">Syncing playlists...</p>
								<p className="text-sm text-gray-600 dark:text-gray-400">
									Fetching your playlists from YouTube
								</p>
							</div>
						</div>
					) : loading ? (
						<div className="flex justify-center items-center h-64">
							<Spinner size="lg" />
						</div>
					) : playlists.length > 0 ? (
						<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
							{playlists.map((playlist) => (
								<Card
									key={playlist.id}
									className="w-full hover:shadow-lg transition-shadow"
								>
									<CardBody className="p-0">
										<div
											role="button"
											tabIndex={0}
											className="relative cursor-pointer"
											onClick={() => handleViewPlaylist(playlist.id)}
											onKeyDown={(e) => {
												if (e.key === "Enter" || e.key === " ") {
													e.preventDefault();
													handleViewPlaylist(playlist.id);
												}
											}}
										>
											<Image
												shadow="sm"
												radius="none"
												width="100%"
												alt={playlist.title}
												className="w-full object-cover h-[180px]"
												src={
													playlist.thumbnail_url || "/placeholder-thumbnail.jpg"
												}
											/>
											<div className="absolute top-2 right-2 bg-black/80 text-white text-xs px-2 py-1 rounded">
												{playlist.video_count} videos
											</div>
										</div>
										<div
											role="button"
											tabIndex={0}
											className="p-3 space-y-2 cursor-pointer"
											onClick={() => handleViewPlaylist(playlist.id)}
											onKeyDown={(e) => {
												if (e.key === "Enter" || e.key === " ") {
													e.preventDefault();
													handleViewPlaylist(playlist.id);
												}
											}}
										>
											<h3 className="font-semibold text-sm line-clamp-2">
												{playlist.title}
											</h3>
											<p className="text-xs text-gray-500">
												{playlist.channel_title}
											</p>
											{playlist.published_at && (
												<p className="text-xs text-gray-400">
													Created{" "}
													{formatDistanceToNow(
														new Date(playlist.published_at),
														{ addSuffix: true },
													)}
												</p>
											)}
											{playlist.last_synced_at && (
												<p className="text-xs text-gray-400">
													Last synced{" "}
													{formatDistanceToNow(
														new Date(playlist.last_synced_at),
														{ addSuffix: true },
													)}
												</p>
											)}
										</div>
									</CardBody>
									<CardFooter className="flex gap-2">
										<Button
											size="sm"
											color="primary"
											variant="flat"
											className="flex-1"
											onPress={() => {
												handleViewPlaylist(playlist.id);
											}}
											radius="md"
										>
											View Videos
										</Button>
										<Button
											size="sm"
											variant="bordered"
											onPress={() => {
												handleViewPlaylist(playlist.id);
											}}
											radius="md"
										>
											YouTube
										</Button>
									</CardFooter>
								</Card>
							))}
						</div>
					) : (
						<div className="text-center py-12">
							<p className="text-gray-500 text-lg">No playlists found</p>
							<p className="text-gray-400 text-sm mt-2">
								Create playlists on YouTube or from the Videos page to see them
								here
							</p>
						</div>
					)}
				</div>
			</div>
		</div>
	);
}
