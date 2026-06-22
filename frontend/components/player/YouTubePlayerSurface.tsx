/// <reference types="youtube" />
"use client";

import { useEffect, useImperativeHandle, useRef } from "react";

// Singleton script loader — safe for multiple instances
let ytScriptStatus: "unloaded" | "loading" | "ready" = "unloaded";
const ytReadyCallbacks: Array<() => void> = [];

function onYTReady(cb: () => void): void {
	if (ytScriptStatus === "ready") {
		cb();
		return;
	}
	ytReadyCallbacks.push(cb);
	if (ytScriptStatus === "unloaded") {
		ytScriptStatus = "loading";
		const tag = document.createElement("script");
		tag.src = "https://www.youtube.com/iframe_api";
		document.head.appendChild(tag);
		window.onYouTubeIframeAPIReady = () => {
			ytScriptStatus = "ready";
			for (const fn of ytReadyCallbacks) fn();
			ytReadyCallbacks.length = 0;
		};
	}
}

export interface YouTubePlayerSurfaceHandle {
	play: () => void;
	pause: () => void;
	getPaused: () => boolean;
	getCurrentTime: () => number;
}

interface YouTubePlayerSurfaceProps {
	youtubeId: string;
	className?: string;
	startSeconds?: number;
	onPlayingChange?: (isPlaying: boolean) => void;
	onEnded?: () => void;
	onError?: () => void;
	ref?: React.Ref<YouTubePlayerSurfaceHandle>;
}

function YouTubePlayerSurface({
	youtubeId,
	className,
	startSeconds,
	onPlayingChange,
	onEnded,
	onError,
	ref,
}: YouTubePlayerSurfaceProps) {
	const containerRef = useRef<HTMLDivElement>(null);
	const playerRef = useRef<YT.Player | null>(null);
	const isPausedRef = useRef(true);
	// Store callbacks in refs so the player isn't recreated when they change
	const onPlayingChangeRef = useRef(onPlayingChange);
	const onEndedRef = useRef(onEnded);
	const onErrorRef = useRef(onError);
	onPlayingChangeRef.current = onPlayingChange;
	onEndedRef.current = onEnded;
	onErrorRef.current = onError;

	useImperativeHandle(ref, () => ({
		play: () => playerRef.current?.playVideo(),
		pause: () => playerRef.current?.pauseVideo(),
		getPaused: () => isPausedRef.current,
		getCurrentTime: () => playerRef.current?.getCurrentTime() ?? 0,
	}));

	useEffect(() => {
		let player: YT.Player | null = null;
		let destroyed = false;

		onYTReady(() => {
			if (destroyed || !containerRef.current) return;
			player = new window.YT.Player(containerRef.current, {
				videoId: youtubeId,
				playerVars: {
					autoplay: 1,
					rel: 0,
					modestbranding: 1,
					playsinline: 1,
					fs: 1,
					...(startSeconds && startSeconds > 0
						? { start: Math.floor(startSeconds) }
						: {}),
				},
				events: {
					onStateChange: (e: YT.OnStateChangeEvent) => {
						const playing = e.data === YT.PlayerState.PLAYING;
						isPausedRef.current = !playing;
						onPlayingChangeRef.current?.(playing);
						if (e.data === YT.PlayerState.ENDED) onEndedRef.current?.();
					},
					onError: () => onErrorRef.current?.(),
				},
			});
			playerRef.current = player;
		});

		return () => {
			destroyed = true;
			player?.destroy();
			playerRef.current = null;
			isPausedRef.current = true;
		};
	}, [youtubeId, startSeconds]);

	return <div ref={containerRef} className={className} />;
}

export default YouTubePlayerSurface;
