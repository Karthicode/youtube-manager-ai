"use client";

import type { InsightsOverview } from "@/types";

interface InsightsSummaryCardsProps {
	data: InsightsOverview | null;
	loading?: boolean;
}

function formatDuration(seconds: number): string {
	if (seconds < 60) return `${seconds}s`;
	if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
	const hours = Math.floor(seconds / 3600);
	const mins = Math.round((seconds % 3600) / 60);
	return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
}

function formatWatchTime(seconds: number): string {
	const hours = Math.floor(seconds / 3600);
	if (hours < 24) return `${hours} hours`;
	const days = Math.floor(hours / 24);
	const remainingHours = hours % 24;
	return remainingHours > 0 ? `${days}d ${remainingHours}h` : `${days} days`;
}

export default function InsightsSummaryCards({
	data,
	loading = false,
}: InsightsSummaryCardsProps) {
	const items = [
		{ label: "Videos", value: (data?.total_videos ?? 0).toLocaleString() },
		{ label: "Channels", value: (data?.unique_channels ?? 0).toLocaleString() },
		{
			label: "Categories",
			value: (data?.unique_categories ?? 0).toLocaleString(),
		},
		{ label: "Tags", value: (data?.unique_tags ?? 0).toLocaleString() },
		{
			label: "Avg Duration",
			value: formatDuration(data?.avg_video_duration_seconds ?? 0),
		},
		{
			label: "Watch Time",
			value: formatWatchTime(data?.total_watch_time_seconds ?? 0),
		},
	];

	return (
		<div className="grid grid-cols-3 lg:grid-cols-6 divide-x divide-y lg:divide-y-0 divide-border bg-surface border border-border rounded-xl overflow-hidden">
			{items.map((item) => (
				<div key={item.label} className="px-3 py-2.5 sm:px-4 sm:py-3">
					<p className="text-[10px] uppercase tracking-widest text-text-secondary">
						{item.label}
					</p>
					<p
						className={`font-mono-editorial text-lg sm:text-xl font-semibold text-text-primary mt-0.5 ${
							loading ? "animate-pulse" : ""
						}`}
					>
						{loading ? "…" : item.value}
					</p>
				</div>
			))}
		</div>
	);
}
