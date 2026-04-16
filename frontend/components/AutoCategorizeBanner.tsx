"use client";

import { Button, Card, CardBody } from "@heroui/react";
import type { AxiosError } from "axios";
import { useState } from "react";
import useSWR, { mutate } from "swr";
import { autoCategorizeApi } from "@/api/api";
import { swrKeys } from "@/lib/swrKeys";
import CategorizationProgressSSE from "./CategorizationProgressSSE";

const STALE_THRESHOLD_HOURS = 36;

type StatusPayload = {
	status: string;
	reason?: string;
	stage?: string;
	error?: string;
	videos_synced?: number;
	videos_categorized?: number;
	job_id?: string;
	user_id?: number;
	timestamp?: string;
};

interface AutoCategorizeBannerProps {
	// User's last_sync_at from the auth store; used to detect stale (>36h) runs
	// for users who have never had an entry recorded in Redis yet.
	lastSyncAt: string | null;
	// Called when a retry job completes (triggered) so the parent can refresh
	// the video stats SWR key.
	onJobComplete?: () => void;
}

function fetchStatus(): Promise<StatusPayload> {
	return autoCategorizeApi.getStatus().then((r) => r.data);
}

function isStale(
	lastSyncAt: string | null,
	timestamp: string | undefined,
): boolean {
	const ref = timestamp ?? lastSyncAt;
	if (!ref) return true;
	const refMs = new Date(ref).getTime();
	if (Number.isNaN(refMs)) return true;
	const ageHours = (Date.now() - refMs) / (1000 * 60 * 60);
	return ageHours >= STALE_THRESHOLD_HOURS;
}

export default function AutoCategorizeBanner({
	lastSyncAt,
	onJobComplete,
}: AutoCategorizeBannerProps) {
	const { data, error } = useSWR<StatusPayload>(
		swrKeys.autoCategorizeStatus(),
		fetchStatus,
		{
			revalidateOnFocus: false,
			shouldRetryOnError: false,
		},
	);

	const [retrying, setRetrying] = useState(false);
	const [retryError, setRetryError] = useState<string | null>(null);
	const [jobId, setJobId] = useState<string | null>(null);

	// While the retry is in flight or the SSE job is running, the banner stays
	// mounted to host the progress UI.
	if (!data && !error && !jobId) return null;
	if (error && !jobId) return null;

	const failed = data?.status === "failed";
	const stale =
		!failed &&
		data?.status !== "triggered" &&
		isStale(lastSyncAt, data?.timestamp);

	// Nothing worth showing — recent successful/skipped run.
	if (!failed && !stale && !jobId && !retrying) return null;

	const handleRetry = async () => {
		setRetrying(true);
		setRetryError(null);
		try {
			const response = await autoCategorizeApi.retry();
			if (response.data.status === "triggered" && response.data.job_id) {
				setJobId(response.data.job_id);
			} else {
				// no_videos / skipped — just refresh status and clear the banner
				await mutate(swrKeys.autoCategorizeStatus());
			}
		} catch (err) {
			const axiosErr = err as AxiosError<{ detail?: { message?: string } }>;
			const detail = axiosErr.response?.data?.detail;
			setRetryError(
				typeof detail === "object" && detail?.message
					? detail.message
					: "Retry failed. Please try again.",
			);
		} finally {
			setRetrying(false);
		}
	};

	const message = failed
		? "Last auto-sync failed."
		: "Auto-sync hasn't run recently.";
	const subMessage = failed
		? data?.stage === "sync"
			? "We couldn't fetch your latest liked videos from YouTube."
			: data?.stage === "trigger"
				? "Sync completed but categorization couldn't be queued."
				: (data?.error ?? "An error occurred during the last run.")
		: "Your liked videos haven't been pulled in the last 36 hours.";

	return (
		<Card className="bg-warning-50 dark:bg-warning-50/10 border border-warning-200 dark:border-warning-200/30 shadow-none">
			<CardBody className="py-3 px-4">
				<div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
					<div className="flex-1 min-w-0">
						<p className="text-sm font-semibold text-text-primary">{message}</p>
						<p className="text-xs text-text-secondary mt-0.5">{subMessage}</p>
						{retryError && (
							<p className="text-xs text-danger mt-1">{retryError}</p>
						)}
					</div>
					{!jobId && (
						<Button
							color="warning"
							size="sm"
							variant="solid"
							onPress={handleRetry}
							isLoading={retrying}
							className="sm:w-auto w-full"
						>
							Retry now
						</Button>
					)}
				</div>
				{jobId && (
					<div className="mt-3">
						<CategorizationProgressSSE
							jobId={jobId}
							onComplete={() => {
								setJobId(null);
								mutate(swrKeys.autoCategorizeStatus());
								onJobComplete?.();
							}}
							onError={(err) => {
								setJobId(null);
								setRetryError(err || "Categorization failed.");
							}}
						/>
					</div>
				)}
			</CardBody>
		</Card>
	);
}
