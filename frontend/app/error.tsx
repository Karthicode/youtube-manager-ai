"use client";

import { Button } from "@heroui/react";

// biome-ignore lint/suspicious/noShadowRestrictedNames: Next.js convention for error boundary components
export default function Error({
	error,
	reset,
}: {
	error: Error & { digest?: string };
	reset: () => void;
}) {
	const goToDashboard = () => {
		window.location.href = "/dashboard";
	};

	return (
		<div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center p-4">
			<div className="text-center space-y-6 max-w-md">
				<div className="space-y-2">
					<h2 className="text-2xl font-bold text-gray-900 dark:text-white">
						Something went wrong
					</h2>
					<p className="text-gray-600 dark:text-gray-400">
						{error.message || "An unexpected error occurred."}
					</p>
				</div>
				<div className="flex gap-3 justify-center">
					<Button color="primary" onPress={reset}>
						Try again
					</Button>
					<Button variant="bordered" onPress={goToDashboard}>
						Go to Dashboard
					</Button>
				</div>
			</div>
		</div>
	);
}
