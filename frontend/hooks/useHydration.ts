"use client";

import { useEffect, useState } from "react";

/**
 * Hook to handle client-side hydration state.
 * Returns true once the component has mounted on the client.
 * Use this to prevent hydration mismatches with SSR.
 */
export function useHydration() {
	const [mounted, setMounted] = useState(false);

	useEffect(() => {
		setMounted(true);
	}, []);

	return mounted;
}
