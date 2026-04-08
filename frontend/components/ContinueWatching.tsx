"use client";

import CloseIcon from "@mui/icons-material/Close";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import Image from "next/image";
import { useCallback, useEffect, useRef, useState } from "react";
import { watchHistoryApi } from "@/api/api";
import { useMiniPlayerStore } from "@/store/miniPlayer";
import type { WatchHistory } from "@/types";

function formatRemaining(
	positionSeconds: number,
	durationSeconds: number | null,
): string {
	if (!durationSeconds) return "";
	const remaining = Math.max(0, durationSeconds - positionSeconds);
	const mins = Math.round(remaining / 60);
	if (mins <= 0) return "Almost done";
	return `${mins} min remaining`;
}

export default function ContinueWatching() {
	const [items, setItems] = useState<WatchHistory[]>([]);
	const [loaded, setLoaded] = useState(false);
	const openPlayer = useMiniPlayerStore((s) => s.openPlayer);
	const isOpen = useMiniPlayerStore((s) => s.isOpen);
	const wasOpenRef = useRef(isOpen);

	const fetchItems = useCallback(() => {
		watchHistoryApi
			.getContinueWatching({ limit: 10 })
			.then((res) => setItems(res.data.items))
			.catch(() => {})
			.finally(() => setLoaded(true));
	}, []);

	useEffect(() => {
		fetchItems();
	}, [fetchItems]);

	useEffect(() => {
		const wasOpen = wasOpenRef.current;
		wasOpenRef.current = isOpen;
		if (wasOpen && !isOpen) {
			const timer = setTimeout(fetchItems, 500);
			return () => clearTimeout(timer);
		}
	}, [isOpen, fetchItems]);

	if (!loaded || items.length === 0) return null;

	const handleResume = (item: WatchHistory) => {
		const video = {
			id: item.video_id,
			youtubeId: item.youtube_id,
			title: item.title,
			channelTitle: item.channel_title,
			thumbnailUrl: item.thumbnail_url,
		};
		openPlayer(
			video,
			[video],
			0,
			{ type: "videos" },
			item.is_completed ? 0 : item.position_seconds,
		);
	};

	const handleRemove = (id: number) => {
		setItems((prev) => prev.filter((i) => i.id !== id));
		watchHistoryApi.deleteEntry(id).catch(() => {});
	};

	return (
		<section className="mb-6">
			<h2 className="text-lg font-semibold mb-3">Continue Watching</h2>
			<div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
				{items.map((item) => (
					<div
						key={item.id}
						className="group relative rounded-xl overflow-hidden border border-default-200 bg-content1 flex flex-col"
					>
						{/* Thumbnail */}
						<div className="relative aspect-video bg-black">
							{item.thumbnail_url ? (
								<Image
									src={item.thumbnail_url}
									alt={item.title}
									fill
									className="object-cover"
									sizes="(max-width: 640px) 50vw, (max-width: 1024px) 25vw, 20vw"
								/>
							) : (
								<div className="w-full h-full bg-default-200" />
							)}
							{/* Progress bar */}
							<div className="absolute bottom-0 left-0 right-0 h-1 bg-default-300/60">
								<div
									className="h-full bg-danger"
									style={{ width: `${Math.min(item.progress_percent, 100)}%` }}
								/>
							</div>
							{/* Remove button */}
							<button
								type="button"
								aria-label="Remove from continue watching"
								className="absolute top-1 right-1 rounded-full bg-black/60 p-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
								onClick={() => handleRemove(item.id)}
							>
								<CloseIcon sx={{ fontSize: 14 }} className="text-white" />
							</button>
						</div>

						{/* Info */}
						<div className="p-2 flex-1 flex flex-col gap-1">
							<p className="text-xs font-semibold line-clamp-2 leading-tight">
								{item.title}
							</p>
							{item.channel_title && (
								<p className="text-[11px] text-default-500 line-clamp-1">
									{item.channel_title}
								</p>
							)}
							{item.duration_seconds && (
								<p className="text-[11px] text-default-400">
									{formatRemaining(
										item.position_seconds,
										item.duration_seconds,
									)}
								</p>
							)}
							<button
								type="button"
								className="mt-auto flex items-center justify-center gap-1 rounded-lg bg-primary text-white text-xs font-medium py-1.5 hover:bg-primary/90 transition-colors"
								onClick={() => handleResume(item)}
							>
								<PlayArrowIcon sx={{ fontSize: 14 }} />
								Resume
							</button>
						</div>
					</div>
				))}
			</div>
		</section>
	);
}
