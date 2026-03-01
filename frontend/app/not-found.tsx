import Link from "next/link";

export default function NotFound() {
	return (
		<div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center p-4">
			<div className="text-center space-y-6 max-w-md">
				<div className="space-y-2">
					<h2 className="text-6xl font-bold text-gray-300 dark:text-gray-700">
						404
					</h2>
					<h3 className="text-2xl font-bold text-gray-900 dark:text-white">
						Page not found
					</h3>
					<p className="text-gray-600 dark:text-gray-400">
						The page you&apos;re looking for doesn&apos;t exist or has been
						moved.
					</p>
				</div>
				<Link
					href="/dashboard"
					className="inline-block px-6 py-3 bg-primary text-white rounded-lg font-medium hover:opacity-90 transition-opacity"
				>
					Go to Dashboard
				</Link>
			</div>
		</div>
	);
}
