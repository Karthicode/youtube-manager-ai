"use client";

import { Card, CardBody } from "@heroui/react";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import CategoryIcon from "@mui/icons-material/Category";
import DateRangeIcon from "@mui/icons-material/DateRange";
import LocalOfferIcon from "@mui/icons-material/LocalOffer";
import PlayCircleIcon from "@mui/icons-material/PlayCircle";
import SubscriptionsIcon from "@mui/icons-material/Subscriptions";
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

function _formatDateRange(
	earliest: string | null,
	latest: string | null,
): string {
	if (!earliest || !latest) return "No data";
	const start = new Date(earliest);
	const end = new Date(latest);
	const startStr = start.toLocaleDateString("en-US", {
		month: "short",
		year: "numeric",
	});
	const endStr = end.toLocaleDateString("en-US", {
		month: "short",
		year: "numeric",
	});
	return startStr === endStr ? startStr : `${startStr} - ${endStr}`;
}

export default function InsightsSummaryCards({
	data,
	loading = false,
}: InsightsSummaryCardsProps) {
	const cards = [
		{
			label: "Total Videos",
			value: data?.total_videos ?? 0,
			icon: PlayCircleIcon,
			color: "from-blue-500 to-blue-600",
			textColor: "text-blue-600 dark:text-blue-400",
		},
		{
			label: "Channels",
			value: data?.unique_channels ?? 0,
			icon: SubscriptionsIcon,
			color: "from-purple-500 to-purple-600",
			textColor: "text-purple-600 dark:text-purple-400",
		},
		{
			label: "Categories",
			value: data?.unique_categories ?? 0,
			icon: CategoryIcon,
			color: "from-green-500 to-green-600",
			textColor: "text-green-600 dark:text-green-400",
		},
		{
			label: "Tags",
			value: data?.unique_tags ?? 0,
			icon: LocalOfferIcon,
			color: "from-orange-500 to-orange-600",
			textColor: "text-orange-600 dark:text-orange-400",
		},
		{
			label: "Avg Duration",
			value: formatDuration(data?.avg_video_duration_seconds ?? 0),
			icon: AccessTimeIcon,
			color: "from-cyan-500 to-cyan-600",
			textColor: "text-cyan-600 dark:text-cyan-400",
			isText: true,
		},
		{
			label: "Total Watch Time",
			value: formatWatchTime(data?.total_watch_time_seconds ?? 0),
			icon: DateRangeIcon,
			color: "from-pink-500 to-pink-600",
			textColor: "text-pink-600 dark:text-pink-400",
			isText: true,
		},
	];

	return (
		<div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 sm:gap-4">
			{cards.map((card) => (
				<Card
					key={card.label}
					className="shadow-md hover:shadow-lg transition-shadow"
				>
					<CardBody className="p-3 sm:p-4">
						<div className="flex items-center gap-2 mb-2">
							<div
								className={`p-1.5 rounded-lg bg-gradient-to-br ${card.color}`}
							>
								<card.icon className="text-white" sx={{ fontSize: 18 }} />
							</div>
							<span className="text-xs text-gray-500 dark:text-gray-400 font-medium">
								{card.label}
							</span>
						</div>
						<p
							className={`text-xl sm:text-2xl font-bold ${card.textColor} ${
								loading ? "animate-pulse" : ""
							}`}
						>
							{loading ? "..." : card.value}
						</p>
					</CardBody>
				</Card>
			))}
		</div>
	);
}
