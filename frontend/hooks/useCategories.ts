import useSWR from "swr";
import { swrKeys } from "@/lib/swrKeys";
import type { Category } from "@/types";

export function useCategories() {
	const { data, error, isLoading, mutate } = useSWR<Category[]>(
		swrKeys.categories(),
		{ revalidateIfStale: false },
	);

	return {
		categories: data ?? [],
		error,
		isLoading,
		mutate,
	};
}
