"use client";

import {
	MediaPlayer,
	type MediaPlayerInstance,
	MediaProvider,
} from "@vidstack/react";
import {
	DefaultVideoLayout,
	defaultLayoutIcons,
} from "@vidstack/react/player/layouts/default";
import { forwardRef, useImperativeHandle, useMemo, useRef } from "react";

const toYouTubeUrl = (youtubeId: string) =>
	`https://www.youtube.com/watch?v=${youtubeId}`;

export interface VidstackYouTubeSurfaceHandle {
	play: () => void;
	pause: () => void;
	getPaused: () => boolean;
}

interface VidstackYouTubeSurfaceProps {
	youtubeId: string;
	className?: string;
	resumeTime?: number;
	onPlayingChange?: (isPlaying: boolean) => void;
	onTimeChange?: (time: number) => void;
	onEnded?: () => void;
	onError?: () => void;
}

const VidstackYouTubeSurface = forwardRef<
	VidstackYouTubeSurfaceHandle,
	VidstackYouTubeSurfaceProps
>(function VidstackYouTubeSurface(
	{
		youtubeId,
		className,
		resumeTime,
		onPlayingChange,
		onTimeChange,
		onEnded,
		onError,
	},
	ref,
) {
	const playerRef = useRef<MediaPlayerInstance>(null);
	const src = useMemo(() => toYouTubeUrl(youtubeId), [youtubeId]);
	const resumeAppliedForSrcRef = useRef<string | null>(null);

	useImperativeHandle(ref, () => ({
		play: () => {
			void playerRef.current?.play();
		},
		pause: () => {
			void playerRef.current?.pause();
		},
		getPaused: () => playerRef.current?.paused ?? true,
	}));

	return (
		<MediaPlayer
			ref={playerRef}
			src={src}
			autoPlay
			playsInline
			className={className}
			onCanPlay={() => {
				const player = playerRef.current;
				if (!player || resumeAppliedForSrcRef.current === src) return;
				resumeAppliedForSrcRef.current = src;
				if (!resumeTime || resumeTime <= 0) return;

				const duration = Number.isFinite(player.duration) ? player.duration : 0;
				const maxSeekTime =
					duration > 0 ? Math.max(duration - 1, 0) : resumeTime;
				player.currentTime = Math.max(0, Math.min(resumeTime, maxSeekTime));
			}}
			onPlay={() => onPlayingChange?.(true)}
			onPause={() => onPlayingChange?.(false)}
			onTimeUpdate={() => {
				const player = playerRef.current;
				if (!player) return;
				onTimeChange?.(player.currentTime ?? 0);
			}}
			onEnded={onEnded}
			onError={() => onError?.()}
		>
			<MediaProvider
				iframeProps={{
					title: "YouTube mini player",
					allow: "autoplay; fullscreen; picture-in-picture",
					loading: "eager",
				}}
			/>
			<DefaultVideoLayout icons={defaultLayoutIcons} noModal />
		</MediaPlayer>
	);
});

export default VidstackYouTubeSurface;
