"use client";

import {
	Button,
	Card,
	CardBody,
	CardFooter,
	Chip,
	Image,
	Tooltip,
} from "@heroui/react";
import { formatDistanceToNow } from "date-fns";
import type { Video } from "@/types";
import { YouTubeEmbed } from "@next/third-parties/google";

interface VideoCardProps {
	video: Video;
	onCategorize?: (videoId: number) => void;
	isCategorizing?: boolean;
	viewMode?: "grid" | "list";
}

export default function VideoCard({
	video,
	onCategorize,
	isCategorizing,
	viewMode = "grid",
}: VideoCardProps) {
	const formatDuration = (seconds: number | null) => {
		if (!seconds) return "Unknown";
		const hours = Math.floor(seconds / 3600);
		const minutes = Math.floor((seconds % 3600) / 60);
		const secs = seconds % 60;

		if (hours > 0) {
			return `${hours}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
		}
		return `${minutes}:${secs.toString().padStart(2, "0")}`;
	};

	const formatViews = (views: number | null) => {
		if (!views) return "0";
		if (views >= 1000000) {
			return `${(views / 1000000).toFixed(1)}M`;
		}
		if (views >= 1000) {
			return `${(views / 1000).toFixed(1)}K`;
		}
		return views.toString();
	};

	const openYouTube = () => {
		window.open(
			`https://www.youtube.com/watch?v=${video.youtube_id}`,
			"_blank",
		);
	};

	// List view - minimal without image
	if (viewMode === "list") {
		return (
			<Card className="w-full hover:shadow-lg transition-shadow">
				<CardBody className="p-3 sm:p-4">
					<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-4">
						<div
							role="button"
							tabIndex={0}
							className="flex-1 min-w-0 cursor-pointer w-full"
							onClick={openYouTube}
							onKeyDown={(e) => {
								if (e.key === "Enter" || e.key === " ") {
									e.preventDefault();
									openYouTube();
								}
							}}
						>
							<h3 className="font-semibold text-sm sm:text-base line-clamp-2 sm:line-clamp-1 mb-1">
								{video.title}
							</h3>
							<div className="flex items-center flex-wrap gap-2 sm:gap-3 text-xs sm:text-sm text-gray-500">
								<span className="truncate">{video.channel_title}</span>
								{video.duration_seconds && (
									<>
										<span>•</span>
										<span>{formatDuration(video.duration_seconds)}</span>
									</>
								)}
								{video.view_count && (
									<>
										<span>•</span>
										<span>{formatViews(video.view_count)} views</span>
									</>
								)}
								{video.published_at && (
									<>
										<span>•</span>
										<span>
											{formatDistanceToNow(new Date(video.published_at), {
												addSuffix: true,
											})}
										</span>
									</>
								)}
							</div>
						</div>

						<div className="flex items-center gap-2 shrink-0 w-full sm:w-auto">
							{video.is_categorized ? (
								<div className="flex flex-wrap gap-1 justify-start sm:justify-end max-w-full sm:max-w-md">
									{video.categories.slice(0, 2).map((category) => (
										<Chip
											key={category.id}
											size="sm"
											color="primary"
											variant="flat"
										>
											{category.name}
										</Chip>
									))}
									{video.tags.slice(0, 2).map((tag) => (
										<Chip key={tag.id} size="sm" variant="bordered">
											{tag.name}
										</Chip>
									))}
									{(video.categories.length > 2 || video.tags.length > 2) && (
										<Chip size="sm" variant="light">
											+{video.categories.length + video.tags.length - 4}
										</Chip>
									)}
								</div>
							) : (
								<>
									<Chip size="sm" color="warning" variant="flat">
										Not categorized
									</Chip>
									{onCategorize && (
										<Button
											size="sm"
											color="primary"
											variant="light"
											isLoading={isCategorizing}
											onPress={() => {
												onCategorize(video.id);
											}}
										>
											Categorize
										</Button>
									)}
								</>
							)}
						</div>
					</div>
				</CardBody>
			</Card>
		);
	}

	// Grid view - original with image (now supports embedded YouTube)
	return (
		<Card className="w-full hover:scale-102 sm:hover:scale-105 transition-transform">
			<CardBody className="p-0">
				{video.youtube_id ? (
					// Embedded player — keep interactions inside the player (no outer click)
					<div className="relative">
						<div className="w-full object-cover h-[160px] sm:h-[200px]">
							<YouTubeEmbed id={video.youtube_id} className="w-full h-full" />
						</div>
						{video.duration_seconds && (
							<div className="absolute bottom-2 right-2 bg-black/80 text-white text-xs px-2 py-1 rounded">
								{formatDuration(video.duration_seconds)}
							</div>
						)}
					</div>
				) : (
					<div
						role="button"
						tabIndex={0}
						className="relative cursor-pointer"
						onClick={openYouTube}
						onKeyDown={(e) => {
							if (e.key === "Enter" || e.key === " ") {
								e.preventDefault();
								openYouTube();
							}
						}}
					>
						<Image
							shadow="sm"
							radius="none"
							width="100%"
							alt={video.title}
							className="w-full object-cover h-[160px] sm:h-[200px]"
							src={video.thumbnail_url || "/placeholder-thumbnail.jpg"}
						/>
						{video.duration_seconds && (
							<div className="absolute bottom-2 right-2 bg-black/80 text-white text-xs px-2 py-1 rounded">
								{formatDuration(video.duration_seconds)}
							</div>
						)}
					</div>
				)}
				<div
					role="button"
					tabIndex={0}
					className="p-2 sm:p-3 space-y-1 sm:space-y-2 cursor-pointer"
					onClick={openYouTube}
					onKeyDown={(e) => {
						if (e.key === "Enter" || e.key === " ") {
							e.preventDefault();
							openYouTube();
						}
					}}
				>
					<Tooltip content={video.title}>
						<h3 className="font-semibold text-xs sm:text-sm line-clamp-2">
							{video.title}
						</h3>
					</Tooltip>
					<p className="text-xs text-gray-500 truncate">
						{video.channel_title}
					</p>
					<div className="flex items-center gap-1 sm:gap-2 text-xs text-gray-400 flex-wrap">
						{video.view_count && (
							<span>{formatViews(video.view_count)} views</span>
						)}
						{video.published_at && (
							<>
								<span>•</span>
								<span>
									{formatDistanceToNow(new Date(video.published_at), {
										addSuffix: true,
									})}
								</span>
							</>
						)}
					</div>
				</div>
			</CardBody>
			<CardFooter className="flex-col items-start gap-2 pt-0">
				{video.is_categorized ? (
					<div className="flex flex-wrap gap-1 w-full">
						{video.categories.slice(0, 3).map((category) => (
							<Chip key={category.id} size="sm" color="primary" variant="flat">
								{category.name}
							</Chip>
						))}
						{video.tags.slice(0, 2).map((tag) => (
							<Chip key={tag.id} size="sm" variant="bordered">
								{tag.name}
							</Chip>
						))}
						{(video.categories.length > 3 || video.tags.length > 2) && (
							<Chip size="sm" variant="light">
								+{video.categories.length + video.tags.length - 5} more
							</Chip>
						)}
					</div>
				) : (
					<div className="flex items-center justify-between w-full">
						<Chip size="sm" color="warning" variant="flat">
							Not categorized
						</Chip>
						{onCategorize && (
							<Button
								size="sm"
								color="primary"
								variant="light"
								isLoading={isCategorizing}
								onPress={() => {
									onCategorize(video.id);
								}}
							>
								Categorize
							</Button>
						)}
					</div>
				)}
			</CardFooter>
		</Card>
	);
}
