"use client";

import { Card, CardBody, Image, Spinner } from "@heroui/react";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import { formatDistanceToNow } from "date-fns";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { playlistsApi } from "@/api/api";
import Navbar from "@/components/Navbar";
import SmartPlaylistDialog from "@/components/SmartPlaylistDialog";
import { useAuthGuard } from "@/hooks";
import type { Playlist } from "@/types";

const containerVariants = {
	hidden: {},
	show: {
		transition: {
			staggerChildren: 0.05,
		},
	},
};

const itemVariants = {
	hidden: { opacity: 0, scale: 0.96 },
	show: {
		opacity: 1,
		scale: 1,
		transition: { duration: 0.3, ease: "easeOut" as const },
	},
};

export default function PlaylistsPage() {
	const router = useRouter();
	const { isReady, isAuthenticated } = useAuthGuard();

	const [playlists, setPlaylists] = useState<Playlist[]>([]);
	const [loading, setLoading] = useState(true);
	const [syncing, setSyncing] = useState(false);
	const [smartDialogOpen, setSmartDialogOpen] = useState(false);

	const fetchPlaylists = useCallback(async () => {
		setLoading(true);
		try {
			const response = await playlistsApi.getPlaylists({ page_size: 50 });
			setPlaylists(response.data);
		} catch {
			// Failed to fetch playlists - UI will show empty state
		} finally {
			setLoading(false);
		}
	}, []);

	const syncPlaylistsFromYouTube = useCallback(async () => {
		setSyncing(true);
		try {
			await playlistsApi.syncPlaylists({ max_results: 50 });
			await fetchPlaylists();
		} catch {
			// Failed to sync playlists - user can retry
		} finally {
			setSyncing(false);
		}
	}, [fetchPlaylists]);

	useEffect(() => {
		if (!isReady || !isAuthenticated) return;
		// Auto-sync playlists on page load
		syncPlaylistsFromYouTube();
	}, [isReady, isAuthenticated, syncPlaylistsFromYouTube]);

	const handleViewPlaylist = (playlistId: number) => {
		router.push(`/playlists/${playlistId}`);
	};

	// Don't render anything until hydrated and authenticated
	if (!isReady || !isAuthenticated) {
		return (
			<div className="min-h-screen bg-[#08080C] flex items-center justify-center">
				<Spinner size="lg" color="primary" />
			</div>
		);
	}

	return (
		<div className="min-h-screen bg-[#08080C]">
			<Navbar />
			<div className="container mx-auto px-4 py-8 max-w-7xl">
				<div className="space-y-6">
					{/* Header */}
					<div className="flex justify-between items-center">
						<div>
							<h1 className="font-display text-3xl font-bold text-[#F2F2F7] tracking-tight">
								Playlists
							</h1>
							<p className="text-[#6B6B7E] mt-1 text-sm">
								{syncing
									? "Syncing with YouTube..."
									: playlists.length > 0
										? `${playlists.length} playlists`
										: "No playlists found"}
							</p>
						</div>
						<button
							type="button"
							onClick={() => setSmartDialogOpen(true)}
							className="flex items-center gap-2 px-4 py-2 bg-[#E63946] text-white font-medium rounded-xl hover:bg-[#d4202e] transition-colors text-sm"
						>
							<AutoAwesomeIcon sx={{ fontSize: 18 }} />
							AI Generate
						</button>
					</div>

					{/* Content */}
					{syncing ? (
						<div className="flex flex-col justify-center items-center h-64 gap-4">
							<Spinner size="lg" color="primary" />
							<div className="text-center space-y-2">
								<p className="text-lg font-semibold text-[#F2F2F7]">
									Syncing playlists...
								</p>
								<p className="text-sm text-[#6B6B7E]">
									Fetching your playlists from YouTube
								</p>
							</div>
						</div>
					) : loading ? (
						<div className="flex justify-center items-center h-64">
							<Spinner size="lg" color="primary" />
						</div>
					) : playlists.length > 0 ? (
						<motion.div
							variants={containerVariants}
							initial="hidden"
							animate="show"
							className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5"
						>
							{playlists.map((playlist) => (
								<motion.div key={playlist.id} variants={itemVariants}>
									<Card
										isPressable
										onPress={() => handleViewPlaylist(playlist.id)}
										className="w-full bg-[#0F0F14] border border-[#1E1E2A] group overflow-hidden shadow-none hover:border-[#2A2A38] transition-colors"
									>
										<CardBody className="p-0">
											{/* Thumbnail */}
											<div className="relative aspect-video overflow-hidden">
												<Image
													radius="none"
													width="100%"
													alt={playlist.title}
													className="w-full object-cover aspect-video group-hover:scale-105 transition-transform duration-300"
													src={
														playlist.thumbnail_url ||
														"/placeholder-thumbnail.jpg"
													}
												/>
												{/* Bottom gradient */}
												<div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-black/70 to-transparent pointer-events-none" />
												{/* Video count badge */}
												<div className="absolute top-2 right-2 glass-dark text-[#F2F2F7] font-mono-editorial text-xs px-2 py-1 rounded-md">
													{playlist.video_count} videos
												</div>
											</div>

											{/* Footer metadata */}
											<div className="p-3 space-y-1">
												<h3 className="font-semibold text-sm line-clamp-2 text-[#F2F2F7]">
													{playlist.title}
												</h3>
												{playlist.last_synced_at && (
													<p className="text-xs text-[#6B6B7E]">
														Synced{" "}
														{formatDistanceToNow(
															new Date(playlist.last_synced_at),
															{ addSuffix: true },
														)}
													</p>
												)}
											</div>
										</CardBody>
									</Card>
								</motion.div>
							))}
						</motion.div>
					) : (
						<div className="text-center py-12 dot-grid rounded-xl">
							<p className="text-[#6B6B7E] text-lg">No playlists found</p>
							<p className="text-[#2A2A38] text-sm mt-2">
								Create playlists on YouTube or from the Videos page to see them
								here
							</p>
						</div>
					)}
				</div>
			</div>

			<SmartPlaylistDialog
				isOpen={smartDialogOpen}
				onClose={() => setSmartDialogOpen(false)}
				onPlaylistCreated={fetchPlaylists}
			/>
		</div>
	);
}
