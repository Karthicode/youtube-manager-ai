"use client";

import CloseIcon from "@mui/icons-material/Close";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import MinimizeIcon from "@mui/icons-material/Minimize";
import PauseIcon from "@mui/icons-material/Pause";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import SkipNextIcon from "@mui/icons-material/SkipNext";
import SkipPreviousIcon from "@mui/icons-material/SkipPrevious";
import Script from "next/script";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMiniPlayerStore } from "@/store/miniPlayer";

declare global {
	interface Window {
		YT?: {
			Player: new (
				element: HTMLElement,
				config: {
					videoId: string;
					width: string;
					height: string;
					playerVars: Record<string, number | string>;
					events: {
						onReady?: () => void;
						onStateChange?: (event: { data: number }) => void;
						onError?: () => void;
					};
				},
			) => {
				destroy: () => void;
				loadVideoById: (videoId: string) => void;
				playVideo: () => void;
				pauseVideo: () => void;
				getPlayerState: () => number;
			};
			PlayerState: {
				ENDED: number;
				PLAYING: number;
				PAUSED: number;
			};
		};
		onYouTubeIframeAPIReady?: () => void;
	}
}

const DESKTOP_MARGIN = 16;
const YOUTUBE_PLAYING_STATE = 1;
const YOUTUBE_PAUSED_STATE = 2;
const YOUTUBE_ENDED_STATE = 0;

const getDesktopDimensions = (isMinimized: boolean) => {
	if (isMinimized) {
		return { width: 320, height: 118 };
	}
	return { width: 380, height: 330 };
};

export default function GlobalMiniPlayer() {
	const {
		isOpen,
		isMinimized,
		isMobileExpanded,
		currentVideo,
		queue,
		queueIndex,
		position,
		playNext,
		playPrev,
		setMinimized,
		setMobileExpanded,
		setPosition,
		closePlayer,
	} = useMiniPlayerStore();

	const [isMobile, setIsMobile] = useState(false);
	const [playerState, setPlayerState] = useState(-1);
	const [isYoutubeApiReady, setIsYoutubeApiReady] = useState(false);
	const [youtubeApiLoadError, setYoutubeApiLoadError] = useState(false);
	const playerContainerRef = useRef<HTMLDivElement | null>(null);
	const playerRef = useRef<{
		destroy: () => void;
		loadVideoById: (videoId: string) => void;
		playVideo: () => void;
		pauseVideo: () => void;
		getPlayerState: () => number;
	} | null>(null);
	const isDraggingRef = useRef(false);
	const dragOffsetRef = useRef({ x: 0, y: 0 });

	const canGoPrevious = queueIndex > 0;
	const canGoNext = queueIndex < queue.length - 1;
	const isPlaying = playerState === YOUTUBE_PLAYING_STATE;
	const desktopDimensions = useMemo(
		() => getDesktopDimensions(isMinimized),
		[isMinimized],
	);

	useEffect(() => {
		if (typeof window === "undefined") return;
		if (window.YT?.Player) {
			setIsYoutubeApiReady(true);
			return;
		}

		const previousReadyHandler = window.onYouTubeIframeAPIReady;
		const handleApiReady = () => {
			previousReadyHandler?.();
			setIsYoutubeApiReady(true);
		};
		window.onYouTubeIframeAPIReady = handleApiReady;

		return () => {
			if (window.onYouTubeIframeAPIReady === handleApiReady) {
				window.onYouTubeIframeAPIReady = previousReadyHandler;
			}
		};
	}, []);

	useEffect(() => {
		if (typeof window === "undefined") return;

		const mediaQuery = window.matchMedia("(max-width: 768px)");
		const updateMobileState = (matches: boolean) => {
			setIsMobile(matches);
		};

		updateMobileState(mediaQuery.matches);

		const handler = (event: MediaQueryListEvent) => {
			updateMobileState(event.matches);
		};

		if (mediaQuery.addEventListener) {
			mediaQuery.addEventListener("change", handler);
			return () => mediaQuery.removeEventListener("change", handler);
		}

		mediaQuery.addListener(handler);
		return () => mediaQuery.removeListener(handler);
	}, []);

	useEffect(() => {
		if (!isOpen || isMobile || typeof window === "undefined") return;

		const applyBounds = () => {
			const maxX = Math.max(
				DESKTOP_MARGIN,
				window.innerWidth - desktopDimensions.width - DESKTOP_MARGIN,
			);
			const maxY = Math.max(
				DESKTOP_MARGIN,
				window.innerHeight - desktopDimensions.height - DESKTOP_MARGIN,
			);

			const nextX =
				position?.x !== undefined
					? Math.min(Math.max(position.x, DESKTOP_MARGIN), maxX)
					: maxX;
			const nextY =
				position?.y !== undefined
					? Math.min(Math.max(position.y, DESKTOP_MARGIN), maxY)
					: maxY;

			if (!position || nextX !== position.x || nextY !== position.y) {
				setPosition({ x: nextX, y: nextY });
			}
		};

		applyBounds();

		const onResize = () => applyBounds();
		window.addEventListener("resize", onResize);
		return () => window.removeEventListener("resize", onResize);
	}, [desktopDimensions, isMobile, isOpen, position, setPosition]);

	useEffect(() => {
		if (!isOpen || isMobile || typeof window === "undefined") return;

		const handlePointerMove = (event: PointerEvent) => {
			if (!isDraggingRef.current) return;

			const maxX = Math.max(
				DESKTOP_MARGIN,
				window.innerWidth - desktopDimensions.width - DESKTOP_MARGIN,
			);
			const maxY = Math.max(
				DESKTOP_MARGIN,
				window.innerHeight - desktopDimensions.height - DESKTOP_MARGIN,
			);

			const x = Math.min(
				Math.max(event.clientX - dragOffsetRef.current.x, DESKTOP_MARGIN),
				maxX,
			);
			const y = Math.min(
				Math.max(event.clientY - dragOffsetRef.current.y, DESKTOP_MARGIN),
				maxY,
			);

			setPosition({ x, y });
		};

		const handlePointerUp = () => {
			isDraggingRef.current = false;
		};

		window.addEventListener("pointermove", handlePointerMove);
		window.addEventListener("pointerup", handlePointerUp);

		return () => {
			window.removeEventListener("pointermove", handlePointerMove);
			window.removeEventListener("pointerup", handlePointerUp);
		};
	}, [desktopDimensions, isMobile, isOpen, setPosition]);

	useEffect(() => {
		if (!isOpen || !currentVideo?.youtubeId || !playerContainerRef.current)
			return;
		if (!isYoutubeApiReady || youtubeApiLoadError) return;

		if (playerRef.current) {
			playerRef.current.loadVideoById(currentVideo.youtubeId);
			playerRef.current.playVideo();
			return;
		}

		if (!window.YT?.Player) return;

		playerRef.current = new window.YT.Player(playerContainerRef.current, {
			videoId: currentVideo.youtubeId,
			width: "100%",
			height: "100%",
			playerVars: {
				autoplay: 1,
				controls: 1,
				playsinline: 1,
				rel: 0,
				modestbranding: 1,
			},
			events: {
				onReady: () => {
					setPlayerState(YOUTUBE_PLAYING_STATE);
				},
				onStateChange: (event) => {
					setPlayerState(event.data);
					if (event.data === YOUTUBE_ENDED_STATE) {
						playNext();
					}
				},
				onError: () => {
					playNext();
				},
			},
		});
	}, [
		currentVideo?.youtubeId,
		isOpen,
		isYoutubeApiReady,
		playNext,
		youtubeApiLoadError,
	]);

	useEffect(() => {
		if (isOpen) return;
		playerRef.current?.destroy();
		playerRef.current = null;
		setPlayerState(-1);
	}, [isOpen]);

	useEffect(() => {
		return () => {
			playerRef.current?.destroy();
			playerRef.current = null;
		};
	}, []);

	if (!isOpen || !currentVideo) {
		return null;
	}

	const handleDragStart = (event: React.PointerEvent<HTMLDivElement>) => {
		if (isMobile || !position) return;
		const target = event.target as HTMLElement;
		if (target.closest("[data-no-drag='true']")) return;

		isDraggingRef.current = true;
		dragOffsetRef.current = {
			x: event.clientX - position.x,
			y: event.clientY - position.y,
		};
	};

	const togglePlayback = () => {
		if (!playerRef.current) return;
		const state = playerRef.current.getPlayerState();
		if (state === YOUTUBE_PLAYING_STATE) {
			playerRef.current.pauseVideo();
			setPlayerState(YOUTUBE_PAUSED_STATE);
			return;
		}

		playerRef.current.playVideo();
		setPlayerState(YOUTUBE_PLAYING_STATE);
	};

	const playerFrame = (
		<div
			className={
				isMobile
					? isMobileExpanded
						? "w-full"
						: "absolute w-px h-px opacity-0 pointer-events-none overflow-hidden"
					: isMinimized
						? "absolute w-px h-px opacity-0 pointer-events-none overflow-hidden"
						: "w-full"
			}
		>
			{youtubeApiLoadError ? (
				<div className="aspect-video w-full rounded-md border border-danger-200 bg-danger-50 text-danger-700 text-xs flex items-center justify-center p-3 text-center">
					Unable to load YouTube player right now.
				</div>
			) : (
				<div className="aspect-video w-full bg-black rounded-md overflow-hidden">
					<div ref={playerContainerRef} className="w-full h-full" />
				</div>
			)}
		</div>
	);

	if (isMobile) {
		return (
			<div className="fixed bottom-4 left-4 right-4 z-[1000] rounded-xl border border-default-200 bg-content1/95 shadow-2xl backdrop-blur">
				{isOpen && !isYoutubeApiReady && (
					<Script
						id="youtube-iframe-api"
						src="https://www.youtube.com/iframe_api"
						strategy="afterInteractive"
						onError={() => setYoutubeApiLoadError(true)}
					/>
				)}
				<div className="p-3 space-y-3">
					{playerFrame}
					<div className="flex items-center gap-2">
						<button
							type="button"
							className="rounded-md p-1.5 hover:bg-default-100"
							onClick={togglePlayback}
							aria-label={isPlaying ? "Pause" : "Play"}
						>
							{isPlaying ? <PauseIcon fontSize="small" /> : <PlayArrowIcon />}
						</button>
						<div className="min-w-0 flex-1">
							<p className="text-xs font-semibold line-clamp-1">
								{currentVideo.title}
							</p>
							<p className="text-[11px] text-default-500 line-clamp-1">
								{currentVideo.channelTitle || "Unknown channel"}
							</p>
						</div>
						<button
							type="button"
							className="rounded-md p-1.5 hover:bg-default-100"
							onClick={() => setMobileExpanded(!isMobileExpanded)}
							aria-label={
								isMobileExpanded ? "Collapse player" : "Expand player"
							}
						>
							{isMobileExpanded ? <ExpandMoreIcon /> : <ExpandLessIcon />}
						</button>
						<button
							type="button"
							className="rounded-md p-1.5 hover:bg-default-100"
							onClick={closePlayer}
							aria-label="Close player"
						>
							<CloseIcon fontSize="small" />
						</button>
					</div>

					{isMobileExpanded && (
						<div className="flex items-center justify-center gap-2">
							<button
								type="button"
								className="rounded-md p-1.5 hover:bg-default-100 disabled:opacity-40"
								onClick={playPrev}
								disabled={!canGoPrevious}
								aria-label="Previous video"
							>
								<SkipPreviousIcon />
							</button>
							<button
								type="button"
								className="rounded-md p-1.5 hover:bg-default-100 disabled:opacity-40"
								onClick={playNext}
								disabled={!canGoNext}
								aria-label="Next video"
							>
								<SkipNextIcon />
							</button>
							<span className="text-xs text-default-500 ml-2">
								{queue.length > 0 ? `${queueIndex + 1} / ${queue.length}` : ""}
							</span>
						</div>
					)}
				</div>
			</div>
		);
	}

	return (
		<div
			className="fixed z-[1000] rounded-xl border border-default-200 bg-content1/95 shadow-2xl backdrop-blur"
			style={{
				width: desktopDimensions.width,
				height: desktopDimensions.height,
				left: position?.x ?? DESKTOP_MARGIN,
				top: position?.y ?? DESKTOP_MARGIN,
			}}
		>
			{isOpen && !isYoutubeApiReady && (
				<Script
					id="youtube-iframe-api"
					src="https://www.youtube.com/iframe_api"
					strategy="afterInteractive"
					onError={() => setYoutubeApiLoadError(true)}
				/>
			)}
			<div
				className="flex items-center gap-2 px-3 py-2 border-b border-default-100 cursor-move select-none"
				onPointerDown={handleDragStart}
			>
				<div className="min-w-0 flex-1">
					<p className="text-xs font-semibold line-clamp-1">
						{currentVideo.title}
					</p>
					<p className="text-[11px] text-default-500 line-clamp-1">
						{currentVideo.channelTitle || "Unknown channel"}
					</p>
				</div>
				<span className="text-[11px] text-default-500">
					{queue.length > 0 ? `${queueIndex + 1} / ${queue.length}` : ""}
				</span>
				<button
					type="button"
					data-no-drag="true"
					className="rounded-md p-1.5 hover:bg-default-100"
					onClick={() => setMinimized(!isMinimized)}
					aria-label={isMinimized ? "Restore player" : "Minimize player"}
				>
					<MinimizeIcon fontSize="small" />
				</button>
				<button
					type="button"
					data-no-drag="true"
					className="rounded-md p-1.5 hover:bg-default-100"
					onClick={closePlayer}
					aria-label="Close player"
				>
					<CloseIcon fontSize="small" />
				</button>
			</div>

			{!isMinimized && <div className="px-3 pt-3 pb-2">{playerFrame}</div>}

			<div className="flex items-center justify-center gap-2 px-3 pb-3">
				<button
					type="button"
					className="rounded-md p-1.5 hover:bg-default-100 disabled:opacity-40"
					onClick={playPrev}
					disabled={!canGoPrevious}
					aria-label="Previous video"
				>
					<SkipPreviousIcon />
				</button>
				<button
					type="button"
					className="rounded-md p-1.5 hover:bg-default-100"
					onClick={togglePlayback}
					aria-label={isPlaying ? "Pause" : "Play"}
				>
					{isPlaying ? <PauseIcon /> : <PlayArrowIcon />}
				</button>
				<button
					type="button"
					className="rounded-md p-1.5 hover:bg-default-100 disabled:opacity-40"
					onClick={playNext}
					disabled={!canGoNext}
					aria-label="Next video"
				>
					<SkipNextIcon />
				</button>
			</div>
		</div>
	);
}
