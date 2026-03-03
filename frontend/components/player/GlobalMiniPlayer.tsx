"use client";

import CloseIcon from "@mui/icons-material/Close";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import MinimizeIcon from "@mui/icons-material/Minimize";
import PauseIcon from "@mui/icons-material/Pause";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import SkipNextIcon from "@mui/icons-material/SkipNext";
import SkipPreviousIcon from "@mui/icons-material/SkipPrevious";
import { useEffect, useRef, useState } from "react";
import { useMiniPlayerStore } from "@/store/miniPlayer";
import VidstackYouTubeSurface, {
	type VidstackYouTubeSurfaceHandle,
} from "./VidstackYouTubeSurface";

const DESKTOP_MARGIN = 16;
const DESKTOP_MIN_WIDTH = 320;
const DESKTOP_MIN_HEIGHT = 260;
const DEFAULT_DESKTOP_SIZE = { width: 380, height: 330 };
const MINIMIZED_DESKTOP_SIZE = { width: 320, height: 118 };

export default function GlobalMiniPlayer() {
	const {
		isOpen,
		isMinimized,
		isMobileExpanded,
		currentVideo,
		queue,
		queueIndex,
		currentTime,
		position,
		playNext,
		playPrev,
		setCurrentTime,
		setMinimized,
		setMobileExpanded,
		setPosition,
		closePlayer,
	} = useMiniPlayerStore();

	const [isMobile, setIsMobile] = useState(false);
	const [isPlaying, setIsPlaying] = useState(false);
	const [playerError, setPlayerError] = useState(false);
	const [desktopSize, setDesktopSize] = useState(DEFAULT_DESKTOP_SIZE);
	const surfaceRef = useRef<VidstackYouTubeSurfaceHandle | null>(null);

	const isDraggingRef = useRef(false);
	const isResizingRef = useRef(false);
	const resizeCornerRef = useRef<"nw" | "ne" | "sw" | "se" | null>(null);
	const resizeStartRef = useRef({
		x: 0,
		y: 0,
		width: DEFAULT_DESKTOP_SIZE.width,
		height: DEFAULT_DESKTOP_SIZE.height,
		left: 0,
		top: 0,
	});
	const dragOffsetRef = useRef({ x: 0, y: 0 });
	const lastPersistedSecondRef = useRef(-1);
	const lastTrackedVideoIdRef = useRef<string | null>(null);

	const canGoPrevious = queueIndex > 0;
	const canGoNext = queueIndex < queue.length - 1;
	const activeDesktopDimensions = isMinimized
		? MINIMIZED_DESKTOP_SIZE
		: desktopSize;

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
			const viewportMaxWidth = Math.max(
				DESKTOP_MIN_WIDTH,
				window.innerWidth - DESKTOP_MARGIN * 2,
			);
			const viewportMaxHeight = Math.max(
				DESKTOP_MIN_HEIGHT,
				window.innerHeight - DESKTOP_MARGIN * 2,
			);

			const nextWidth = Math.min(
				Math.max(desktopSize.width, DESKTOP_MIN_WIDTH),
				viewportMaxWidth,
			);
			const nextHeight = Math.min(
				Math.max(desktopSize.height, DESKTOP_MIN_HEIGHT),
				viewportMaxHeight,
			);

			if (!isMinimized) {
				if (
					nextWidth !== desktopSize.width ||
					nextHeight !== desktopSize.height
				) {
					setDesktopSize({ width: nextWidth, height: nextHeight });
				}
			}

			const maxX = Math.max(
				DESKTOP_MARGIN,
				window.innerWidth - activeDesktopDimensions.width - DESKTOP_MARGIN,
			);
			const maxY = Math.max(
				DESKTOP_MARGIN,
				window.innerHeight - activeDesktopDimensions.height - DESKTOP_MARGIN,
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
	}, [
		activeDesktopDimensions.height,
		activeDesktopDimensions.width,
		desktopSize.height,
		desktopSize.width,
		isMinimized,
		isMobile,
		isOpen,
		position,
		setPosition,
	]);

	useEffect(() => {
		if (!isOpen || isMobile || typeof window === "undefined") return;

		const handlePointerMove = (event: PointerEvent) => {
			if (isResizingRef.current && !isMinimized) {
				const corner = resizeCornerRef.current;
				if (!corner) return;

				const start = resizeStartRef.current;
				const rightEdge = start.left + start.width;
				const bottomEdge = start.top + start.height;
				const dx = event.clientX - start.x;
				const dy = event.clientY - start.y;

				let nextWidth = start.width;
				let nextHeight = start.height;

				if (corner === "se" || corner === "ne") {
					nextWidth = start.width + dx;
				}
				if (corner === "sw" || corner === "nw") {
					nextWidth = start.width - dx;
				}
				if (corner === "se" || corner === "sw") {
					nextHeight = start.height + dy;
				}
				if (corner === "ne" || corner === "nw") {
					nextHeight = start.height - dy;
				}

				const viewportMaxWidth = Math.max(
					DESKTOP_MIN_WIDTH,
					window.innerWidth - DESKTOP_MARGIN * 2,
				);
				const viewportMaxHeight = Math.max(
					DESKTOP_MIN_HEIGHT,
					window.innerHeight - DESKTOP_MARGIN * 2,
				);

				nextWidth = Math.min(
					Math.max(nextWidth, DESKTOP_MIN_WIDTH),
					viewportMaxWidth,
				);
				nextHeight = Math.min(
					Math.max(nextHeight, DESKTOP_MIN_HEIGHT),
					viewportMaxHeight,
				);

				let nextX =
					corner === "sw" || corner === "nw"
						? rightEdge - nextWidth
						: start.left;
				let nextY =
					corner === "ne" || corner === "nw"
						? bottomEdge - nextHeight
						: start.top;

				nextX = Math.min(
					Math.max(nextX, DESKTOP_MARGIN),
					window.innerWidth - DESKTOP_MARGIN - nextWidth,
				);
				nextY = Math.min(
					Math.max(nextY, DESKTOP_MARGIN),
					window.innerHeight - DESKTOP_MARGIN - nextHeight,
				);

				if (corner === "sw" || corner === "nw") {
					nextWidth = rightEdge - nextX;
				}
				if (corner === "ne" || corner === "nw") {
					nextHeight = bottomEdge - nextY;
				}

				setDesktopSize({ width: nextWidth, height: nextHeight });
				setPosition({ x: nextX, y: nextY });
				return;
			}

			if (!isDraggingRef.current) return;

			const maxX = Math.max(
				DESKTOP_MARGIN,
				window.innerWidth - activeDesktopDimensions.width - DESKTOP_MARGIN,
			);
			const maxY = Math.max(
				DESKTOP_MARGIN,
				window.innerHeight - activeDesktopDimensions.height - DESKTOP_MARGIN,
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
			isResizingRef.current = false;
			resizeCornerRef.current = null;
		};

		window.addEventListener("pointermove", handlePointerMove);
		window.addEventListener("pointerup", handlePointerUp);

		return () => {
			window.removeEventListener("pointermove", handlePointerMove);
			window.removeEventListener("pointerup", handlePointerUp);
		};
	}, [
		activeDesktopDimensions.height,
		activeDesktopDimensions.width,
		isMinimized,
		isMobile,
		isOpen,
		setPosition,
	]);

	useEffect(() => {
		if (!isOpen) {
			setIsPlaying(false);
			setPlayerError(false);
		}
	}, [isOpen]);

	useEffect(() => {
		if (!isOpen || !currentVideo?.youtubeId) return;
		setPlayerError(false);
	}, [currentVideo?.youtubeId, isOpen]);

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

	const handleResizeStart = (
		corner: "nw" | "ne" | "sw" | "se",
		event: React.PointerEvent<HTMLDivElement>,
	) => {
		if (isMobile || isMinimized || !position) return;

		event.preventDefault();
		event.stopPropagation();

		isResizingRef.current = true;
		resizeCornerRef.current = corner;
		resizeStartRef.current = {
			x: event.clientX,
			y: event.clientY,
			width: desktopSize.width,
			height: desktopSize.height,
			left: position.x,
			top: position.y,
		};
	};

	const togglePlayback = () => {
		const isPaused = surfaceRef.current?.getPaused() ?? true;
		if (isPaused) {
			surfaceRef.current?.play();
			return;
		}
		surfaceRef.current?.pause();
	};

	const handleTimeChange = (nextTime: number) => {
		if (!Number.isFinite(nextTime) || nextTime < 0) return;
		if (lastTrackedVideoIdRef.current !== currentVideo.youtubeId) {
			lastTrackedVideoIdRef.current = currentVideo.youtubeId;
			lastPersistedSecondRef.current = -1;
		}
		const roundedSecond = Math.floor(nextTime);
		if (roundedSecond === lastPersistedSecondRef.current) return;
		lastPersistedSecondRef.current = roundedSecond;
		setCurrentTime(roundedSecond);
	};

	const playerFrame = (
		<div
			className={
				isMobile
					? isMobileExpanded
						? "w-full"
						: "absolute w-px h-px opacity-0 pointer-events-none overflow-hidden"
					: "w-full h-full"
			}
		>
			{playerError ? (
				<div className="w-full h-full rounded-md border border-danger-200 bg-danger-50 text-danger-700 text-xs flex items-center justify-center p-3 text-center">
					Unable to load YouTube player right now.
				</div>
			) : (
				<VidstackYouTubeSurface
					ref={surfaceRef}
					youtubeId={currentVideo.youtubeId}
					className={`rounded-md overflow-hidden bg-black ${isMobile ? "w-full aspect-video" : "w-full h-full"}`}
					resumeTime={currentTime}
					onPlayingChange={setIsPlaying}
					onTimeChange={handleTimeChange}
					onEnded={playNext}
					onError={() => {
						setPlayerError(true);
						playNext();
					}}
				/>
			)}
		</div>
	);

	if (isMobile) {
		return (
			<div className="fixed bottom-4 left-4 right-4 z-[1000] rounded-xl border border-default-200 bg-content1/95 shadow-2xl backdrop-blur">
				<div className="p-3 space-y-3">
					{playerFrame}
					<div className="flex items-center gap-2">
						{!isMobileExpanded && (
							<button
								type="button"
								className="rounded-md p-1.5 hover:bg-default-100"
								onClick={togglePlayback}
								aria-label={isPlaying ? "Pause" : "Play"}
							>
								{isPlaying ? <PauseIcon fontSize="small" /> : <PlayArrowIcon />}
							</button>
						)}
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
			className="fixed z-[1000] rounded-xl border border-default-200 bg-content1/95 shadow-2xl backdrop-blur flex flex-col"
			style={{
				width: activeDesktopDimensions.width,
				height: activeDesktopDimensions.height,
				left: position?.x ?? DESKTOP_MARGIN,
				top: position?.y ?? DESKTOP_MARGIN,
			}}
		>
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

			<div
				className={
					isMinimized
						? "h-0 overflow-hidden px-0 py-0"
						: "px-3 pt-3 pb-2 flex-1 min-h-0"
				}
			>
				{playerFrame}
			</div>

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
				{isMinimized && (
					<button
						type="button"
						className="rounded-md p-1.5 hover:bg-default-100"
						onClick={togglePlayback}
						aria-label={isPlaying ? "Pause" : "Play"}
					>
						{isPlaying ? <PauseIcon /> : <PlayArrowIcon />}
					</button>
				)}
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
			{!isMinimized && (
				<>
					<div
						data-no-drag="true"
						className="absolute -top-1 -left-1 w-3 h-3 rounded-full bg-default-300 cursor-nwse-resize"
						onPointerDown={(event) => handleResizeStart("nw", event)}
					/>
					<div
						data-no-drag="true"
						className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-default-300 cursor-nesw-resize"
						onPointerDown={(event) => handleResizeStart("ne", event)}
					/>
					<div
						data-no-drag="true"
						className="absolute -bottom-1 -left-1 w-3 h-3 rounded-full bg-default-300 cursor-nesw-resize"
						onPointerDown={(event) => handleResizeStart("sw", event)}
					/>
					<div
						data-no-drag="true"
						className="absolute -bottom-1 -right-1 w-3 h-3 rounded-full bg-default-300 cursor-nwse-resize"
						onPointerDown={(event) => handleResizeStart("se", event)}
					/>
				</>
			)}
		</div>
	);
}
