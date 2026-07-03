"use client";

import { Button } from "@heroui/react";
import type { AxiosError } from "axios";
import { formatDistanceToNow } from "date-fns";
import { useState } from "react";
import useSWR, { mutate } from "swr";
import { authApi, autoCategorizeApi } from "@/api/api";
import { swrKeys } from "@/lib/swrKeys";
import type { VideoStats } from "@/types";
import CategorizationProgressSSE from "./CategorizationProgressSSE";

const STALE_THRESHOLD_HOURS = 36;

type StatusPayload = {
	status: string;
	reason?: string;
	stage?: string;
	error?: string;
	error_type?: string;
	videos_synced?: number;
	videos_categorized?: number;
	job_id?: string;
	user_id?: number;
	timestamp?: string;
};

interface LibraryStatusStripProps {
	// User's last_sync_at from the auth store; drives the sync-recency segment
	// and staleness detection for users with no Redis status entry yet.
	lastSyncAt: string | null;
	// Called when a retry job completes so the parent can refresh video stats.
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

export default function LibraryStatusStrip({
	lastSyncAt,
	onJobComplete,
}: LibraryStatusStripProps) {
	const { data: status, error: statusError } = useSWR<StatusPayload>(
		swrKeys.autoCategorizeStatus(),
		fetchStatus,
		{ revalidateOnFocus: false, shouldRetryOnError: false },
	);
	const { data: stats } = useSWR<VideoStats>(swrKeys.videoStats());

	const [retrying, setRetrying] = useState(false);
	const [retryError, setRetryError] = useState<string | null>(null);
	const [jobId, setJobId] = useState<string | null>(null);

	const failed = !statusError && status?.status === "failed";
	const stale =
		!failed &&
		status?.status !== "triggered" &&
		isStale(lastSyncAt, status?.timestamp);
	const healthy = !failed && !stale;

	const dotColor = failed
		? "bg-[#E63946]"
		: stale
			? "bg-[#F59E0B]"
			: "bg-[#10b981]";

	const syncLabel = lastSyncAt
		? `Synced ${formatDistanceToNow(new Date(lastSyncAt), { addSuffix: true })}`
		: "Never synced";

	const problemMessage = failed
		? status?.stage === "sync"
			? "Last auto-sync failed — couldn't fetch your liked videos."
			: status?.stage === "trigger"
				? "Sync completed but categorization couldn't be queued."
				: "Last auto-sync failed."
		: "Auto-sync hasn't run in the last 36 hours.";

	const handleRetry = async () => {
		setRetrying(true);
		setRetryError(null);
		try {
			const response = await autoCategorizeApi.retry();
			if (response.data.status === "triggered" && response.data.job_id) {
				setJobId(response.data.job_id);
			} else {
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

	const isAuthFailure = failed && status?.error_type === "auth";

	const handleReconnect = async () => {
		setRetrying(true);
		try {
			const response = await authApi.getLoginUrl();
			window.location.href = response.data.auth_url;
		} catch {
			setRetryError("Couldn't start YouTube reconnect. Please try again.");
			setRetrying(false);
		}
	};

	return (
		<div className="bg-surface border border-border rounded-xl px-4 py-2.5">
			<div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-text-secondary">
				{/* Sync recency */}
				<span className="flex items-center gap-2">
					<span className={`h-2 w-2 rounded-full ${dotColor}`} />
					<span>{syncLabel}</span>
				</span>

				{/* Categorization progress */}
				{stats && (
					<span className="flex items-center gap-2">
						<span className="w-24 h-1 bg-border rounded-full overflow-hidden">
							<span
								className="block h-full bg-[#E63946] rounded-full transition-all duration-700"
								style={{ width: `${stats.categorization_percentage}%` }}
							/>
						</span>
						<span className="font-mono-editorial text-text-primary">
							{stats.categorization_percentage.toFixed(1)}%
						</span>
						<span>categorized</span>
					</span>
				)}

				{/* Auto-sync problem + action (silent when healthy) */}
				{!healthy && !jobId && (
					<span className="flex items-center gap-3 sm:ml-auto">
						<span className={failed ? "text-[#E63946]" : "text-[#F59E0B]"}>
							{isAuthFailure ? "YouTube connection expired." : problemMessage}
						</span>
						{isAuthFailure ? (
							<Button
								color="danger"
								size="sm"
								variant="flat"
								onPress={handleReconnect}
								isLoading={retrying}
							>
								Reconnect YouTube
							</Button>
						) : (
							<Button
								color="warning"
								size="sm"
								variant="flat"
								onPress={handleRetry}
								isLoading={retrying}
							>
								Retry now
							</Button>
						)}
					</span>
				)}
			</div>

			{retryError && <p className="text-xs text-danger mt-2">{retryError}</p>}

			{failed && !isAuthFailure && status?.error && (
				<p className="text-xs text-text-secondary mt-1 line-clamp-1">
					{status.error}
				</p>
			)}

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
		</div>
	);
}
