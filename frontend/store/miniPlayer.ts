import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface MiniPlayerVideo {
	id: number;
	youtubeId: string;
	title: string;
	channelTitle: string | null;
	thumbnailUrl: string | null;
}

export interface MiniPlayerQueueItem {
	id: number;
	youtubeId: string;
	title: string;
	channelTitle: string | null;
	thumbnailUrl: string | null;
}

export interface MiniPlayerContext {
	type: "playlist" | "videos";
	playlistId?: number;
	playlistTitle?: string | null;
	sourceTab?: "liked";
	semanticSearch?: boolean;
	query?: string | null;
}

export interface MiniPlayerPosition {
	x: number;
	y: number;
}

interface MiniPlayerState {
	isOpen: boolean;
	isMinimized: boolean;
	isMobileExpanded: boolean;
	currentVideo: MiniPlayerVideo | null;
	queue: MiniPlayerQueueItem[];
	queueIndex: number;
	position: MiniPlayerPosition | null;
	originContext: MiniPlayerContext | null;
	resumeSeconds: number | null;
	openPlayer: (
		video: MiniPlayerVideo,
		queue: MiniPlayerQueueItem[],
		index: number,
		context: MiniPlayerContext,
		resumeSeconds?: number,
	) => void;
	playAtIndex: (index: number) => void;
	playNext: () => void;
	playPrev: () => void;
	setMinimized: (isMinimized: boolean) => void;
	setMobileExpanded: (expanded: boolean) => void;
	setPosition: (position: MiniPlayerPosition) => void;
	closePlayer: () => void;
}

const clampQueueIndex = (index: number, length: number) => {
	if (length <= 0) return 0;
	if (index < 0) return 0;
	if (index >= length) return length - 1;
	return index;
};

export const useMiniPlayerStore = create<MiniPlayerState>()(
	persist(
		(set, get) => ({
			isOpen: false,
			isMinimized: false,
			isMobileExpanded: false,
			currentVideo: null,
			queue: [],
			queueIndex: 0,
			position: null,
			originContext: null,
			resumeSeconds: null,

			openPlayer: (video, queue, index, context, resumeSeconds) => {
				const safeQueue = queue.length > 0 ? queue : [video];
				const safeIndex = clampQueueIndex(index, safeQueue.length);
				const queuedVideo = safeQueue[safeIndex];

				set({
					isOpen: true,
					isMinimized: false,
					currentVideo: queuedVideo,
					queue: safeQueue,
					queueIndex: safeIndex,
					originContext: context,
					isMobileExpanded: false,
					resumeSeconds: resumeSeconds ?? null,
				});
			},

			playAtIndex: (index) => {
				const queue = get().queue;
				if (queue.length === 0) return;
				const safeIndex = clampQueueIndex(index, queue.length);
				set({
					queueIndex: safeIndex,
					currentVideo: queue[safeIndex],
					resumeSeconds: null,
				});
			},

			playNext: () => {
				const { queue, queueIndex } = get();
				if (queue.length === 0) return;
				if (queueIndex >= queue.length - 1) return;
				const nextIndex = queueIndex + 1;
				set({
					queueIndex: nextIndex,
					currentVideo: queue[nextIndex],
					resumeSeconds: null,
				});
			},

			playPrev: () => {
				const { queue, queueIndex } = get();
				if (queue.length === 0) return;
				if (queueIndex <= 0) return;
				const prevIndex = queueIndex - 1;
				set({
					queueIndex: prevIndex,
					currentVideo: queue[prevIndex],
					resumeSeconds: null,
				});
			},

			setMinimized: (isMinimized) => set({ isMinimized }),

			setMobileExpanded: (expanded) => set({ isMobileExpanded: expanded }),

			setPosition: (position) => set({ position }),

			closePlayer: () =>
				set({
					isOpen: false,
					isMinimized: false,
					isMobileExpanded: false,
					currentVideo: null,
					queue: [],
					queueIndex: 0,
					originContext: null,
					resumeSeconds: null,
				}),
		}),
		{
			name: "mini-player-storage",
			partialize: (state) => ({
				isMinimized: state.isMinimized,
				position: state.position,
			}),
		},
	),
);
