"use client";

import { Button, Card, CardBody, Progress } from "@heroui/react";
import { useEffect, useState } from "react";
import { videosApi } from "@/api/api";

interface ProgressData {
	status: "running" | "completed" | "error" | "paused" | "cancelled";
	total: number;
	completed: number;
	failed: number;
	current_video: string | null;
	paused: boolean;
	error?: string;
}

interface CategorizationProgressSSEProps {
	jobId: string | null;
	onComplete?: () => void;
	onError?: (error: string) => void;
}

export default function CategorizationProgressSSE({
	jobId,
	onComplete,
	onError,
}: CategorizationProgressSSEProps) {
	const [progress, setProgress] = useState<ProgressData>({
		status: "running",
		total: 0,
		completed: 0,
		failed: 0,
		current_video: null,
		paused: false,
	});
	const [pauseLoading, setPauseLoading] = useState(false);

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
		const sseUrl = `${apiBaseUrl}/videos/categorize-batch/stream/${jobId}`;

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
								const data: ProgressData = JSON.parse(line.substring(6));
								setProgress(data);

								// Handle completion
								if (data.status === "completed") {
									onComplete?.();
									isCancelled = true;
									break;
								}

								// Handle error
								if (data.status === "error") {
									onError?.(data.error || "Categorization failed");
									isCancelled = true;
									break;
								}

								// Handle cancellation
								if (data.status === "cancelled") {
									onComplete?.(); // Still refresh stats to show partial progress
									isCancelled = true;
									break;
								}
							} catch (error) {
								console.error("Failed to parse SSE data:", error);
							}
						}
					}
				}
			} catch (error) {
				if (!isCancelled) {
					console.error("SSE connection error:", error);
					onError?.(
						error instanceof Error ? error.message : "Connection failed",
					);
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

	const handlePause = async () => {
		if (!jobId) return;
		setPauseLoading(true);
		try {
			await videosApi.pauseCategorizationJob(jobId);
		} catch (error) {
			console.error("Failed to pause job:", error);
			alert("Failed to pause job. Please try again.");
		} finally {
			setPauseLoading(false);
		}
	};

	const handleResume = async () => {
		if (!jobId) return;
		setPauseLoading(true);
		try {
			await videosApi.resumeCategorizationJob(jobId);
		} catch (error) {
			console.error("Failed to resume job:", error);
			alert("Failed to resume job. Please try again.");
		} finally {
			setPauseLoading(false);
		}
	};

	const handleCancel = async () => {
		if (!jobId) return;
		if (!confirm("Are you sure you want to cancel categorization? This cannot be undone.")) {
			return;
		}
		try {
			await videosApi.cancelCategorizationJob(jobId);
			// The SSE will automatically close when it receives cancelled status
		} catch (error) {
			console.error("Failed to cancel job:", error);
			alert("Failed to cancel job. Please try again.");
		}
	};

	// Don't show anything if no job
	if (!jobId) return null;

	const progressPercentage =
		progress.total > 0 ? (progress.completed / progress.total) * 100 : 0;

	return (
		<Card className="mb-4">
			<CardBody className="space-y-3 sm:space-y-4 p-4 sm:p-6">
				<div className="flex justify-between items-center gap-3">
					<h3 className="font-semibold text-base sm:text-lg">
						Categorization Progress
					</h3>
					<div className="flex items-center gap-2 sm:gap-3">
						{(progress.status === "running" || progress.paused) && (
							<>
								{progress.status === "running" && !progress.paused && (
									<Button
										size="sm"
										color="warning"
										variant="flat"
										onPress={handlePause}
										isLoading={pauseLoading}
										className="min-w-20"
									>
										Pause
									</Button>
								)}
								{progress.paused && (
									<Button
										size="sm"
										color="success"
										variant="flat"
										onPress={handleResume}
										isLoading={pauseLoading}
										className="min-w-20"
									>
										Resume
									</Button>
								)}
								<Button
									size="sm"
									color="danger"
									variant="flat"
									onPress={handleCancel}
									className="min-w-20"
								>
									Cancel
								</Button>
							</>
						)}
						<span className="text-sm text-gray-600 dark:text-gray-400 whitespace-nowrap">
							{progress.completed} / {progress.total}
						</span>
					</div>
				</div>

				<Progress
					value={progressPercentage}
					color={
						progress.status === "error"
							? "danger"
							: progress.paused
								? "warning"
								: progress.failed > 0
									? "warning"
									: "success"
					}
					className="w-full"
					showValueLabel
				/>

				{progress.paused && (
					<p className="text-sm text-warning font-medium">
						⏸ Paused - Click Resume to continue processing
					</p>
				)}

				{progress.current_video &&
					progress.status === "running" &&
					!progress.paused && (
						<p className="text-sm text-gray-600 dark:text-gray-400 truncate">
							Currently processing: {progress.current_video}
						</p>
					)}

				{progress.failed > 0 && (
					<p className="text-sm text-warning">
						{progress.failed} video(s) failed to categorize
					</p>
				)}

				{progress.status === "running" && !progress.paused && (
					<p className="text-xs text-gray-500 dark:text-gray-500">
						Processing videos in parallel with AI... Don't close this page.
					</p>
				)}

				{progress.status === "completed" && (
					<div className="space-y-2">
						<p className="text-sm text-success font-medium">
							✓ Categorization complete!
						</p>
						<p className="text-xs text-gray-500">
							Successfully categorized {progress.completed} out of{" "}
							{progress.total} videos
							{progress.failed > 0 && ` (${progress.failed} failed)`}
						</p>
					</div>
				)}

				{progress.status === "error" && (
					<div className="space-y-2">
						<p className="text-sm text-danger font-medium">
							✗ Categorization failed
						</p>
						{progress.error && (
							<p className="text-xs text-gray-500">{progress.error}</p>
						)}
					</div>
				)}

				{progress.status === "cancelled" && (
					<div className="space-y-2">
						<p className="text-sm text-warning font-medium">
							⊘ Categorization cancelled
						</p>
						<p className="text-xs text-gray-500">
							Processed {progress.completed} out of {progress.total} videos
							before cancellation
							{progress.failed > 0 && ` (${progress.failed} failed)`}
						</p>
					</div>
				)}
			</CardBody>
		</Card>
	);
}
