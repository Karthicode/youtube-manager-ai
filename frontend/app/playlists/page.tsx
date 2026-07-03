"use client";

import {
	Card,
	CardBody,
	Image,
	Skeleton,
	Spinner,
	Tooltip,
} from "@heroui/react";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import SyncIcon from "@mui/icons-material/Sync";
import { formatDistanceToNow } from "date-fns";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
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
	const [initialLoading, setInitialLoading] = useState(true);
	const [syncing, setSyncing] = useState(false);
	const [syncError, setSyncError] = useState(false);
	const [smartDialogOpen, setSmartDialogOpen] = useState(false);

	// Guard against out-of-order fetch responses overwriting newer data.
	// Only the most recent fetchPlaylists call may write state.
	const fetchSeq = useRef(0);

	const fetchPlaylists = useCallback(async () => {
		const seq = ++fetchSeq.current;
		try {
			const response = await playlistsApi.getPlaylists({ page_size: 50 });
			if (seq === fetchSeq.current) {
				setPlaylists(response.data);
			}
		} catch {
			// Failed to fetch playlists - UI will show empty state
		} finally {
			setInitialLoading(false);
		}
	}, []);

	const syncPlaylistsFromYouTube = useCallback(async () => {
		setSyncing(true);
		setSyncError(false);
		try {
			await playlistsApi.syncPlaylists({ max_results: 50 });
			await fetchPlaylists();
		} catch {
			setSyncError(true);
		} finally {
			setSyncing(false);
		}
	}, [fetchPlaylists]);

	useEffect(() => {
		if (!isReady || !isAuthenticated) return;
		// Cached-first: render stored playlists immediately, refresh from
		// YouTube in the background.
		fetchPlaylists();
		syncPlaylistsFromYouTube();
	}, [isReady, isAuthenticated, fetchPlaylists, syncPlaylistsFromYouTube]);

	const handleViewPlaylist = (playlistId: number) => {
		router.push(`/playlists/${playlistId}`);
	};

	// Don't render anything until hydrated and authenticated
	if (!isReady || !isAuthenticated) {
		return (
			<div className="min-h-screen bg-background flex items-center justify-center">
				<Spinner size="lg" color="primary" />
			</div>
		);
	}

	return (
		<div className="min-h-screen bg-background">
			<Navbar />
			<div className="container mx-auto px-4 py-8 max-w-7xl">
				<div className="space-y-6">
					{/* Header */}
					<div className="flex justify-between items-center">
						<div>
							<h1 className="font-display text-3xl font-bold text-text-primary tracking-tight">
								Playlists
							</h1>
							<p className="mt-1 text-sm text-text-secondary">
								{playlists.length > 0
									? `${playlists.length} playlists`
									: initialLoading
										? "Loading…"
										: "No playlists found"}
								{syncing && (
									<span className="ml-2 text-text-secondary">· Syncing…</span>
								)}
								{!syncing && syncError && (
									<span className="ml-2 text-[#F59E0B]">
										· Sync failed — showing saved playlists
									</span>
								)}
							</p>
						</div>
						<div className="flex items-center gap-2">
							<Tooltip content="Sync from YouTube">
								<button
									type="button"
									onClick={syncPlaylistsFromYouTube}
									disabled={syncing}
									className="flex items-center gap-2 px-4 py-2 bg-surface text-text-primary font-medium rounded-xl hover:bg-surface-elevated transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed border border-border"
								>
									<SyncIcon
										sx={{ fontSize: 18 }}
										className={syncing ? "animate-spin" : ""}
									/>
									Sync
								</button>
							</Tooltip>
							<button
								type="button"
								onClick={() => setSmartDialogOpen(true)}
								className="flex items-center gap-2 px-4 py-2 bg-[#E63946] text-white font-medium rounded-xl hover:bg-[#d4202e] transition-colors text-sm"
							>
								<AutoAwesomeIcon sx={{ fontSize: 18 }} />
								AI Generate
							</button>
						</div>
					</div>

					{/* Content */}
					{initialLoading && playlists.length === 0 ? (
						<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
							{Array.from({ length: 8 }).map((_, i) => (
								<div
									// biome-ignore lint/suspicious/noArrayIndexKey: Static skeleton placeholders
									key={i}
									className="rounded-xl border border-border overflow-hidden"
								>
									<Skeleton className="aspect-video w-full" />
									<div className="p-3 space-y-2">
										<Skeleton className="h-4 w-3/4 rounded" />
										<Skeleton className="h-3 w-1/2 rounded" />
									</div>
								</div>
							))}
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
										className="w-full bg-surface border border-border group overflow-hidden shadow-none hover:border-surface-elevated transition-colors"
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
												<h3 className="font-semibold text-sm line-clamp-2 text-text-primary">
													{playlist.title}
												</h3>
												{playlist.last_synced_at && (
													<p className="text-xs text-text-secondary">
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
							<p className="text-text-secondary text-lg">No playlists found</p>
							<p className="text-text-secondary/60 text-sm mt-2">
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
