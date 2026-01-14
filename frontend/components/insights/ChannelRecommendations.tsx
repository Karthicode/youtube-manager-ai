"use client";

import {
	Avatar,
	Button,
	Card,
	CardBody,
	CardHeader,
	Chip,
	Progress,
	Spinner,
} from "@heroui/react";
import type { ChannelRecommendation } from "@/types";

interface ChannelRecommendationsProps {
	recommendations: ChannelRecommendation[];
	topCategories: string[];
	topTags: string[];
	totalAnalyzed: number;
	loading?: boolean;
	error?: string;
}

function formatSubscriberCount(count: number | null): string {
	if (count === null) return "N/A";
	if (count >= 1_000_000) {
		return `${(count / 1_000_000).toFixed(1)}M`;
	}
	if (count >= 1_000) {
		return `${(count / 1_000).toFixed(1)}K`;
	}
	return count.toString();
}

function ChannelCard({ channel }: { channel: ChannelRecommendation }) {
	const matchPercentage = Math.round(channel.score * 100);

	return (
		<Card className="shadow-md hover:shadow-lg transition-shadow">
			<CardBody className="p-4">
				<div className="flex gap-4">
					{/* Channel Thumbnail */}
					<Avatar
						src={channel.thumbnail_url || undefined}
						alt={channel.channel_title}
						className="w-16 h-16 flex-shrink-0"
						showFallback
						name={channel.channel_title.charAt(0)}
					/>

					{/* Channel Info */}
					<div className="flex-1 min-w-0">
						<h4 className="font-semibold text-sm sm:text-base truncate">
							{channel.channel_title}
						</h4>

						{/* Stats Row */}
						<div className="flex flex-wrap items-center gap-2 mt-1 text-xs text-gray-500 dark:text-gray-400">
							{channel.subscriber_count !== null && (
								<span>
									{formatSubscriberCount(channel.subscriber_count)} subscribers
								</span>
							)}
							{channel.video_count !== null && (
								<>
									<span className="hidden sm:inline">|</span>
									<span>{channel.video_count} videos</span>
								</>
							)}
						</div>

						{/* Match Score */}
						<div className="mt-2">
							<div className="flex items-center justify-between text-xs mb-1">
								<span className="text-gray-600 dark:text-gray-400">Match</span>
								<span className="font-medium text-primary">
									{matchPercentage}%
								</span>
							</div>
							<Progress
								size="sm"
								value={matchPercentage}
								color={
									matchPercentage >= 70
										? "success"
										: matchPercentage >= 50
											? "primary"
											: "warning"
								}
								className="h-1.5"
							/>
						</div>

						{/* Recommendation Reason */}
						<p className="text-xs text-gray-500 dark:text-gray-400 mt-2 line-clamp-2">
							{channel.recommendation_reason}
						</p>
					</div>
				</div>

				{/* Action Button */}
				<div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
					<Button
						as="a"
						href={`https://www.youtube.com/channel/${channel.channel_id}`}
						target="_blank"
						rel="noopener noreferrer"
						size="sm"
						color="danger"
						variant="flat"
						className="w-full"
					>
						Visit Channel
					</Button>
				</div>
			</CardBody>
		</Card>
	);
}

export default function ChannelRecommendations({
	recommendations,
	topCategories,
	topTags,
	totalAnalyzed,
	loading = false,
	error,
}: ChannelRecommendationsProps) {
	return (
		<Card className="shadow-lg">
			<CardHeader className="pb-2">
				<div className="flex flex-col gap-2 w-full">
					<div className="flex items-center gap-2">
						<svg
							className="w-5 h-5 text-primary"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							aria-hidden="true"
						>
							<path
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth={2}
								d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
							/>
						</svg>
						<div>
							<h3 className="text-base sm:text-lg font-semibold">
								Recommended Channels
							</h3>
							<p className="text-xs sm:text-sm text-gray-500 dark:text-gray-400">
								Based on {totalAnalyzed} channels you watch
							</p>
						</div>
					</div>

					{/* Preference Tags */}
					{(topCategories.length > 0 || topTags.length > 0) && (
						<div className="flex flex-wrap gap-1.5 mt-1">
							{topCategories.slice(0, 3).map((cat) => (
								<Chip key={cat} size="sm" color="primary" variant="flat">
									{cat}
								</Chip>
							))}
							{topTags.slice(0, 4).map((tag) => (
								<Chip key={tag} size="sm" color="secondary" variant="flat">
									{tag}
								</Chip>
							))}
						</div>
					)}
				</div>
			</CardHeader>
			<CardBody className="pt-2">
				{loading ? (
					<div className="h-[200px] flex items-center justify-center">
						<Spinner size="lg" />
					</div>
				) : error ? (
					<div className="h-[200px] flex items-center justify-center">
						<p className="text-red-500 text-sm">{error}</p>
					</div>
				) : recommendations.length === 0 ? (
					<div className="h-[200px] flex flex-col items-center justify-center text-gray-500 dark:text-gray-400">
						<svg
							className="w-12 h-12 mb-2 opacity-50"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							aria-hidden="true"
						>
							<path
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth={1.5}
								d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
							/>
						</svg>
						<p className="text-sm">No recommendations yet</p>
						<p className="text-xs mt-1">
							Like more videos to get personalized suggestions
						</p>
					</div>
				) : (
					<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
						{recommendations.map((channel) => (
							<ChannelCard key={channel.channel_id} channel={channel} />
						))}
					</div>
				)}
			</CardBody>
		</Card>
	);
}
