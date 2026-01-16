"use client";

import { Button, Card, CardBody, Progress } from "@heroui/react";
import { useEffect, useState } from "react";
import { videosApi } from "@/api/api";
import type { DeleteProgressData } from "@/types";

interface DeleteProgressSSEProps {
	jobId: string | null;
	onComplete?: () => void;
	onError?: (error: string) => void;
}

export default function DeleteProgressSSE({
	jobId,
	onComplete,
	onError,
}: DeleteProgressSSEProps) {
	const [progress, setProgress] = useState<DeleteProgressData>({
		status: "running",
		total: 0,
		unliked: 0,
		deleted: 0,
		failed: 0,
		current_video: null,
		failures: [],
	});
	const [showFailures, setShowFailures] = useState(false);

	useEffect(() => {
		if (!jobId) return;

		let isCancelled = false;
		const abortController = new AbortController();

		// Get auth token
		const token = localStorage.getItem("access_token");
		if (!token) {
			onError?.("No authentication token found");
			return;
		}

		// Construct SSE URL
		const apiBaseUrl =
			process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
		const sseUrl = `${apiBaseUrl}/videos/delete-by-tags/stream/${jobId}`;

		// Use fetch with ReadableStream to support custom headers
		const connectSSE = async () => {
			try {
				const response = await fetch(sseUrl, {
					headers: {
						Authorization: `Bearer ${token}`,
						Accept: "text/event-stream",
					},
					signal: abortController.signal,
				});

				if (!response.ok) {
					throw new Error(`HTTP ${response.status}: ${response.statusText}`);
				}

				const reader = response.body?.getReader();
				const decoder = new TextDecoder();

				if (!reader) {
					throw new Error("No response body");
				}

				while (!isCancelled) {
					const { done, value } = await reader.read();

					if (done) break;

					const chunk = decoder.decode(value);
					const lines = chunk.split("\n");

					for (const line of lines) {
						if (line.startsWith("data: ")) {
							try {
								const data: DeleteProgressData = JSON.parse(line.substring(6));
								setProgress(data);

								switch (data.status) {
									case "completed":
										onComplete?.();
										isCancelled = true;
										break;

									case "error":
										onError?.(data.error || "Deletion failed");
										isCancelled = true;
										break;

									case "cancelled":
										onComplete?.(); // Still refresh to show partial progress
										isCancelled = true;
										break;
								}

								if (isCancelled) break;
							} catch {
								// Failed to parse SSE data - ignore malformed events
							}
						}
					}
				}
			} catch {
				if (!isCancelled) {
					onError?.("Connection failed");
				}
			}
		};

		connectSSE();

		// Cleanup on unmount
		return () => {
			isCancelled = true;
			abortController.abort();
		};
	}, [jobId, onComplete, onError]);

	const handleCancel = async () => {
		if (!jobId) return;
		if (
			!confirm("Cancel deletion? Videos already deleted cannot be recovered.")
		) {
			return;
		}
		try {
			await videosApi.cancelDeleteJob(jobId);
			// The SSE will automatically close when it receives cancelled status
		} catch {
			alert("Failed to cancel job. Please try again.");
		}
	};

	// Don't show anything if no job
	if (!jobId) return null;

	const progressPercentage =
		progress.total > 0 ? (progress.deleted / progress.total) * 100 : 0;

	// Format percentage to avoid showing 100% when not complete
	const formattedPercentage =
		progress.deleted >= progress.total
			? "100%"
			: `${Math.floor(progressPercentage)}%`;

	return (
		<Card className="mb-4 border-danger-200 dark:border-danger-800">
			<CardBody className="space-y-3 sm:space-y-4 p-4 sm:p-6">
				<div className="flex justify-between items-center gap-3">
					<h3 className="font-semibold text-base sm:text-lg text-danger">
						Deleting Videos
					</h3>
					<div className="flex items-center gap-2 sm:gap-3">
						{progress.status === "running" && (
							<Button
								size="sm"
								color="danger"
								variant="flat"
								onPress={handleCancel}
								className="min-w-20"
							>
								Cancel
							</Button>
						)}
						<span className="text-sm text-gray-600 dark:text-gray-400 whitespace-nowrap">
							{progress.deleted} / {progress.total}
						</span>
					</div>
				</div>

				<Progress
					value={progressPercentage}
					color={
						progress.status === "error"
							? "danger"
							: progress.failed > 0
								? "warning"
								: "danger"
					}
					className="w-full"
					showValueLabel={false}
				/>

				{/* Custom percentage label */}
				<div className="text-center">
					<span className="text-sm font-medium text-gray-700 dark:text-gray-300">
						{formattedPercentage}
					</span>
				</div>

				{/* Stats row */}
				<div className="flex justify-between text-sm text-gray-600 dark:text-gray-400">
					<span>Unliked: {progress.unliked}</span>
					<span>Deleted: {progress.deleted}</span>
					{progress.failed > 0 && (
						<span className="text-warning">Failed: {progress.failed}</span>
					)}
				</div>

				{progress.current_video && progress.status === "running" && (
					<p className="text-sm text-gray-600 dark:text-gray-400 truncate">
						Processing: {progress.current_video}
					</p>
				)}

				{progress.status === "running" && (
					<p className="text-xs text-gray-500 dark:text-gray-500">
						Unliking videos on YouTube and deleting from database... Don't close
						this page.
					</p>
				)}

				{progress.status === "completed" && (
					<div className="space-y-2">
						<p className="text-sm text-success font-medium">
							Deletion complete!
						</p>
						<p className="text-xs text-gray-500">
							Successfully deleted {progress.deleted} out of {progress.total}{" "}
							videos
							{progress.failed > 0 && ` (${progress.failed} failed)`}
						</p>
					</div>
				)}

				{progress.status === "error" && (
					<div className="space-y-2">
						<p className="text-sm text-danger font-medium">Deletion failed</p>
						{progress.error && (
							<p className="text-xs text-gray-500">{progress.error}</p>
						)}
					</div>
				)}

				{progress.status === "cancelled" && (
					<div className="space-y-2">
						<p className="text-sm text-warning font-medium">
							Deletion cancelled
						</p>
						<p className="text-xs text-gray-500">
							Deleted {progress.deleted} out of {progress.total} videos before
							cancellation
							{progress.failed > 0 && ` (${progress.failed} failed)`}
						</p>
					</div>
				)}

				{/* Failures section */}
				{progress.failed > 0 &&
					progress.failures &&
					progress.failures.length > 0 && (
						<div className="mt-2">
							<Button
								size="sm"
								variant="light"
								color="warning"
								onPress={() => setShowFailures(!showFailures)}
							>
								{showFailures ? "Hide" : "Show"} {progress.failed} failure
								{progress.failed !== 1 ? "s" : ""}
							</Button>
							{showFailures && (
								<div className="mt-2 max-h-40 overflow-y-auto bg-gray-50 dark:bg-gray-900 rounded-lg p-2">
									{progress.failures.map((f) => (
										<div
											key={f.video_id}
											className="text-xs text-danger py-1 border-b border-gray-200 dark:border-gray-700 last:border-0"
										>
											<p className="font-medium truncate">{f.title}</p>
											<p className="text-gray-500">{f.error}</p>
										</div>
									))}
								</div>
							)}
						</div>
					)}
			</CardBody>
		</Card>
	);
}
