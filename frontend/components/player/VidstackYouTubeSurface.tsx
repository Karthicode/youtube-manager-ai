"use client";

import {
	MediaPlayer,
	type MediaPlayerInstance,
	MediaProvider,
} from "@vidstack/react";
import { forwardRef, useImperativeHandle, useMemo, useRef } from "react";

const toYouTubeUrl = (youtubeId: string) =>
	`https://www.youtube.com/watch?v=${youtubeId}&controls=1&fs=1&playsinline=1&rel=0&modestbranding=1`;

export interface VidstackYouTubeSurfaceHandle {
	play: () => void;
	pause: () => void;
	getPaused: () => boolean;
}

interface VidstackYouTubeSurfaceProps {
	youtubeId: string;
	className?: string;
	onPlayingChange?: (isPlaying: boolean) => void;
	onEnded?: () => void;
	onError?: () => void;
}

const VidstackYouTubeSurface = forwardRef<
	VidstackYouTubeSurfaceHandle,
	VidstackYouTubeSurfaceProps
>(function VidstackYouTubeSurface(
	{ youtubeId, className, onPlayingChange, onEnded, onError },
	ref,
) {
	const playerRef = useRef<MediaPlayerInstance>(null);
	const src = useMemo(() => toYouTubeUrl(youtubeId), [youtubeId]);

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
			controls
			className={className}
			onPlay={() => onPlayingChange?.(true)}
			onPause={() => onPlayingChange?.(false)}
			onEnded={onEnded}
			onError={() => onError?.()}
		>
			<MediaProvider
				className="w-full h-full"
				iframeProps={{
					title: "YouTube mini player",
					allow: "autoplay; fullscreen; picture-in-picture",
					loading: "eager",
					className: "w-full h-full",
					style: { width: "100%", height: "100%" },
				}}
			/>
		</MediaPlayer>
	);
});

export default VidstackYouTubeSurface;
