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
				<CardBody className="p-4">
					<div className="flex items-center justify-between gap-4">
						<div
							className="flex-1 min-w-0 cursor-pointer"
							onClick={openYouTube}
						>
							<h3 className="font-semibold text-base line-clamp-1 mb-1">
								{video.title}
							</h3>
							<div className="flex items-center gap-3 text-sm text-gray-500">
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

						<div className="flex items-center gap-2 shrink-0">
							{video.is_categorized ? (
								<div className="flex flex-wrap gap-1 justify-end max-w-md">
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
											onPress={(e) => {
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

	// Grid view - original with image
	return (
		<Card className="w-full hover:scale-105 transition-transform">
			<CardBody className="p-0">
				<div className="relative cursor-pointer" onClick={openYouTube}>
					<Image
						shadow="sm"
						radius="none"
						width="100%"
						alt={video.title}
						className="w-full object-cover h-[200px]"
						src={video.thumbnail_url || "/placeholder-thumbnail.jpg"}
					/>
					{video.duration_seconds && (
						<div className="absolute bottom-2 right-2 bg-black/80 text-white text-xs px-2 py-1 rounded">
							{formatDuration(video.duration_seconds)}
						</div>
					)}
				</div>
				<div className="p-3 space-y-2 cursor-pointer" onClick={openYouTube}>
					<Tooltip content={video.title}>
						<h3 className="font-semibold text-sm line-clamp-2">
							{video.title}
						</h3>
					</Tooltip>
					<p className="text-xs text-gray-500">{video.channel_title}</p>
					<div className="flex items-center gap-2 text-xs text-gray-400">
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
								onPress={(e) => {
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
