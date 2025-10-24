"use client";

import { Spinner } from "@heroui/react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api } from "@/api/api";
import { useAuthStore } from "@/store/auth";

function AuthCallbackContent() {
	const router = useRouter();
	const searchParams = useSearchParams();
	const { setAuth } = useAuthStore();
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		const handleCallback = async () => {
			console.log("🔄 OAuth callback received");

			// Check if we received tokens from backend redirect
			const accessToken = searchParams.get("access_token");
			const refreshToken = searchParams.get("refresh_token");
			const userParam = searchParams.get("user");
			const errorParam = searchParams.get("error");

			if (errorParam) {
				console.error("❌ OAuth error:", errorParam);
				setError("Authentication failed. Please try again.");
				setTimeout(() => router.push("/"), 3000);
				return;
			}

			if (accessToken && refreshToken && userParam) {
				console.log("✅ Received tokens from backend redirect");
				try {
					// Parse user data
					const user = JSON.parse(
						decodeURIComponent(userParam.replace(/'/g, '"')),
					);
					console.log("👤 User data:", user);

					// Store auth data
					setAuth(user, accessToken, refreshToken);

					// Also store in localStorage for API interceptor
					localStorage.setItem("access_token", accessToken);
					localStorage.setItem("refresh_token", refreshToken);

					console.log(
						"🎉 Authentication successful! Redirecting to dashboard...",
					);
					// Redirect to dashboard
					router.push("/dashboard");
				} catch (err) {
					console.error("❌ Failed to parse user data:", err);
					setError("Failed to process authentication. Please try again.");
					setTimeout(() => router.push("/"), 3000);
				}
				return;
			}

			// Fallback: old flow (shouldn't be used anymore but kept for compatibility)
			const code = searchParams.get("code");
			const state = searchParams.get("state");

			if (!code || !state) {
				console.error("❌ No tokens or OAuth code found");
				setError("Invalid callback parameters.");
				setTimeout(() => router.push("/"), 3000);
				return;
			}

			console.warn("⚠️ Using legacy callback flow - this shouldn't happen");
			setError("Unexpected callback format. Please try again.");
			setTimeout(() => router.push("/"), 3000);
		};

		handleCallback();
	}, [searchParams, router, setAuth]);

	return (
		<div className="flex min-h-screen flex-col items-center justify-center p-24 bg-linear-to-br from-gray-900 via-gray-800 to-gray-900">
			<div className="text-center space-y-6">
				{error ? (
					<>
						<div className="text-red-400 text-xl">{error}</div>
						<p className="text-gray-400">Redirecting to home...</p>
					</>
				) : (
					<>
						<Spinner size="lg" color="primary" />
						<div className="text-white text-xl">Authenticating...</div>
						<p className="text-gray-400">
							Please wait while we complete your sign-in
						</p>
					</>
				)}
			</div>
		</div>
	);
}

export default function AuthCallback() {
	return (
		<Suspense
			fallback={
				<div className="flex min-h-screen flex-col items-center justify-center p-24 bg-linear-to-br from-gray-900 via-gray-800 to-gray-900">
					<Spinner size="lg" color="primary" />
				</div>
			}
		>
			<AuthCallbackContent />
		</Suspense>
	);
}
