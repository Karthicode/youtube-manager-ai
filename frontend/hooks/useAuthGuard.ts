"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { type User, useAuthStore } from "@/store/auth";
import { useHydration } from "./useHydration";

interface AuthGuardResult {
	isReady: boolean;
	isAuthenticated: boolean;
	user: User | null;
}

/**
 * Hook to guard protected routes.
 * Handles hydration, authentication check, and redirect to login.
 *
 * @param redirectTo - Path to redirect when not authenticated (default: "/")
 * @returns Object with isReady (hydrated + auth checked), isAuthenticated, and user
 */
export function useAuthGuard(redirectTo = "/"): AuthGuardResult {
	const router = useRouter();
	const mounted = useHydration();
	const { isAuthenticated, isHydrated, user } = useAuthStore();

	const isReady = mounted && isHydrated;

	useEffect(() => {
		if (!isReady) return;

		if (!isAuthenticated) {
			router.push(redirectTo);
		}
	}, [isReady, isAuthenticated, router, redirectTo]);

	return {
		isReady,
		isAuthenticated,
		user,
	};
}
