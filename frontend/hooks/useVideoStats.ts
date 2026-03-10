import useSWR from "swr";
import { swrKeys } from "@/lib/swrKeys";
import type { VideoStats } from "@/types";

export function useVideoStats() {
	const { data, error, isLoading, mutate } = useSWR<VideoStats>(
		swrKeys.videoStats(),
	);

	return {
		stats: data ?? null,
		error,
		isLoading,
		mutate,
	};
}
