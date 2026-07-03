import useSWR from "swr";
import { api } from "@/api/api";
import { swrKeys } from "@/lib/swrKeys";
import type {
	CategoryDistribution,
	ChannelStats,
	DurationBucket,
	InsightsOverview,
	TagDistribution,
	TemporalData,
} from "@/types";

function paramFetcher([url, params]: [string, Record<string, unknown>]) {
	return api.get(url, { params }).then((res) => res.data);
}

export function useInsightsOverview() {
	const { data, error, isLoading, mutate } = useSWR<InsightsOverview>(
		swrKeys.insightsOverview(),
		{ revalidateIfStale: false },
	);
	return { data: data ?? null, error, isLoading, mutate };
}

export function useInsightsContentDist() {
	const { data, error, isLoading, mutate } = useSWR<{
		categories: CategoryDistribution[];
		tags: TagDistribution[];
	}>(swrKeys.insightsContentDist(), { revalidateIfStale: false });
	return {
		categories: data?.categories ?? [],
		tags: data?.tags ?? [],
		error,
		isLoading,
		mutate,
	};
}

export function useInsightsChannels(limit = 10) {
	const key = swrKeys.insightsChannels(limit);
	const { data, error, isLoading, mutate } = useSWR<{
		top_channels: ChannelStats[];
	}>(key, {
		fetcher: paramFetcher,
		revalidateIfStale: false,
	});
	return { channels: data?.top_channels ?? [], error, isLoading, mutate };
}

export function useInsightsTemporal() {
	const { data, error, isLoading, mutate } = useSWR<{
		likes_by_month: TemporalData[];
	}>(swrKeys.insightsTemporal(), { revalidateIfStale: false });
	return { temporal: data?.likes_by_month ?? [], error, isLoading, mutate };
}

export function useInsightsDuration() {
	const { data, error, isLoading, mutate } = useSWR<{
		buckets: DurationBucket[];
		avg_duration_seconds: number;
	}>(swrKeys.insightsDuration(), { revalidateIfStale: false });
	return {
		buckets: data?.buckets ?? [],
		avgDuration: data?.avg_duration_seconds ?? 0,
		error,
		isLoading,
		mutate,
	};
}
