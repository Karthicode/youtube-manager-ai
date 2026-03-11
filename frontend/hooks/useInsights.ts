import useSWR from "swr";
import { api } from "@/api/api";
import { swrKeys } from "@/lib/swrKeys";
import type {
	CategoryDistribution,
	ChannelRecommendation,
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
		channels: ChannelStats[];
	}>(key, {
		fetcher: paramFetcher,
		revalidateIfStale: false,
	});
	return { channels: data?.channels ?? [], error, isLoading, mutate };
}

export function useInsightsTemporal() {
	const { data, error, isLoading, mutate } = useSWR<{
		by_month: TemporalData[];
	}>(swrKeys.insightsTemporal(), { revalidateIfStale: false });
	return { temporal: data?.by_month ?? [], error, isLoading, mutate };
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

export function useInsightsRecommendations(limit = 10) {
	const key = swrKeys.insightsRecommendations(limit);
	const { data, error, isLoading, mutate } = useSWR<{
		recommendations: ChannelRecommendation[];
		top_categories: string[];
		top_tags: string[];
		total_analyzed_channels: number;
	}>(key, {
		fetcher: paramFetcher,
		revalidateIfStale: false,
	});
	return {
		items: data?.recommendations ?? [],
		topCategories: data?.top_categories ?? [],
		topTags: data?.top_tags ?? [],
		totalAnalyzed: data?.total_analyzed_channels ?? 0,
		error,
		isLoading,
		mutate,
	};
}
