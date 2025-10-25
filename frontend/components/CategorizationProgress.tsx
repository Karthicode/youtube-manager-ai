// "use client";

// import { Card, CardBody, Progress } from "@heroui/react";
// import { useEffect, useState } from "react";
// import { progressApi } from "@/api/api";

// interface ProgressData {
// 	status: "idle" | "in_progress" | "completed";
// 	total: number;
// 	completed: number;
// 	failed: number;
// 	current_video: string | null;
// }

// interface CategorizationProgressProps {
// 	onComplete?: () => void;
// }

// export default function CategorizationProgress({
// 	onComplete,
// }: CategorizationProgressProps) {
// 	const [progress, setProgress] = useState<ProgressData>({
// 		status: "idle",
// 		total: 0,
// 		completed: 0,
// 		failed: 0,
// 		current_video: null,
// 	});
// 	const [isPolling, setIsPolling] = useState(false);

// 	useEffect(() => {
// 		let intervalId: NodeJS.Timeout | null = null;

// 		const pollProgress = async () => {
// 			try {
// 				const response = await progressApi.getCategorizationProgress();
// 				const data = response.data as ProgressData;
// 				setProgress(data);

// 				// If categorization is complete or idle, stop polling
// 				if (data.status === "in_progress" || data.status === "completed") {
// 					setIsPolling(false);
// 					if (data.status === "completed" && onComplete) {
// 						onComplete();
// 					}
// 				} else {
// 					setIsPolling(true);
// 				}
// 			} catch (error) {
// 				console.error("Failed to fetch progress:", error);
// 			}
// 		};

// 		// Start polling when component mounts
// 		pollProgress();

// 		// Set up interval to poll every second if in progress
// 		if (isPolling || progress.status === "in_progress") {
// 			intervalId = setInterval(pollProgress, 1000);
// 		}

// 		return () => {
// 			if (intervalId) {
// 				clearInterval(intervalId);
// 			}
// 		};
// 	}, [isPolling, progress.status, onComplete]);

// 	// Don't show anything if idle and no work has been done
// 	if (progress.status === "idle" && progress.total === 0) {
// 		return null;
// 	}

// 	const progressPercentage =
// 		progress.total > 0 ? (progress.completed / progress.total) * 100 : 0;

// 	return (
// 		<Card className="mb-4">
// 			<CardBody className="space-y-3">
// 				<div className="flex justify-between items-center">
// 					<h3 className="font-semibold">Categorization Progress</h3>
// 					<span className="text-sm text-gray-600 dark:text-gray-400">
// 						{progress.completed} / {progress.total}
// 					</span>
// 				</div>

// 				<Progress
// 					value={progressPercentage}
// 					color={progress.failed > 0 ? "warning" : "success"}
// 					className="w-full"
// 					showValueLabel
// 				/>

// 				{progress.current_video && (
// 					<p className="text-sm text-gray-600 dark:text-gray-400 truncate">
// 						Currently processing: {progress.current_video}
// 					</p>
// 				)}

// 				{progress.failed > 0 && (
// 					<p className="text-sm text-warning">
// 						{progress.failed} video(s) failed to categorize
// 					</p>
// 				)}

// 				{progress.status === "in_progress" && (
// 					<p className="text-xs text-gray-500 dark:text-gray-500">
// 						Processing in parallel with AI... Don't refresh the page.
// 					</p>
// 				)}

// 				{progress.status === "completed" && (
// 					<p className="text-sm text-success font-medium">
// 						✓ Categorization complete!
// 					</p>
// 				)}
// 			</CardBody>
// 		</Card>
// 	);
// }
