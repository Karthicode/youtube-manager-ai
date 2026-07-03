"use client";

import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { videosApi } from "@/api/api";
import { useMiniPlayerStore } from "@/store/miniPlayer";
import type { Video } from "@/types";

export default function RecentlyLiked() {
	const [videos, setVideos] = useState<Video[]>([]);
	const [loaded, setLoaded] = useState(false);
	const openPlayer = useMiniPlayerStore((s) => s.openPlayer);

	useEffect(() => {
		videosApi
			.getLikedVideos({ limit: 10, sort_by: "liked_at", sort_order: "desc" })
			.then((res) => setVideos(res.data.videos ?? []))
			.catch(() => {})
			.finally(() => setLoaded(true));
	}, []);

	if (!loaded || videos.length === 0) return null;

	const handlePlay = (index: number) => {
		const queue = videos.map((v) => ({
			id: v.id,
			youtubeId: v.youtube_id,
			title: v.title,
			channelTitle: v.channel_title,
			thumbnailUrl: v.thumbnail_url,
		}));
		openPlayer(queue[index], queue, index, {
			type: "videos",
			sourceTab: "liked",
		});
	};

	return (
		<section>
			<div className="flex items-center justify-between mb-3">
				<h2 className="text-lg font-semibold">Recently Liked</h2>
				<Link
					href="/videos"
					className="text-xs text-text-secondary hover:text-[#E63946] transition-colors"
				>
					View all →
				</Link>
			</div>
			<div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
				{videos.map((video, index) => (
					<button
						key={video.id}
						type="button"
						onClick={() => handlePlay(index)}
						className="group relative rounded-xl overflow-hidden border border-border bg-surface flex flex-col text-left"
					>
						{/* Thumbnail */}
						<div className="relative aspect-video bg-black">
							{video.thumbnail_url ? (
								<Image
									src={video.thumbnail_url}
									alt={video.title}
									fill
									className="object-cover"
									sizes="(max-width: 640px) 50vw, (max-width: 1024px) 25vw, 20vw"
								/>
							) : (
								<div className="w-full h-full bg-surface-elevated" />
							)}
							{/* Play overlay */}
							<div className="absolute inset-0 flex items-center justify-center bg-black/0 group-hover:bg-black/40 transition-colors">
								<PlayArrowIcon
									sx={{ fontSize: 32 }}
									className="text-white opacity-0 group-hover:opacity-100 transition-opacity"
								/>
							</div>
						</div>

						{/* Info */}
						<div className="p-2 flex-1 flex flex-col gap-1">
							<p className="text-xs font-semibold line-clamp-2 leading-tight text-text-primary">
								{video.title}
							</p>
							{video.channel_title && (
								<p className="text-[11px] text-text-secondary line-clamp-1">
									{video.channel_title}
								</p>
							)}
						</div>
					</button>
				))}
			</div>
		</section>
	);
}
