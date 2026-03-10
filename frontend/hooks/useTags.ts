import useSWR from "swr";
import { api } from "@/api/api";
import { swrKeys } from "@/lib/swrKeys";
import type { Tag } from "@/types";

function tagsFetcher([url, params]: [string, { limit?: number }]) {
	return api.get<Tag[]>(url, { params }).then((res) => res.data);
}

export function useTags(limit?: number) {
	const key = swrKeys.tags(limit ? { limit } : undefined);
	const { data, error, isLoading, mutate } = useSWR<Tag[]>(key, {
		fetcher: Array.isArray(key) ? tagsFetcher : undefined,
		revalidateIfStale: false,
	});

	return {
		tags: data ?? [],
		error,
		isLoading,
		mutate,
	};
}
