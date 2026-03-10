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
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import { YouTubeEmbed } from "@next/third-parties/google";
import { formatDistanceToNow } from "date-fns";
import type { Video } from "@/types";

interface VideoCardProps {
	video: Video;
	onCategorize?: (videoId: number) => void;
	onPlay?: (video: Video) => void;
	isCategorizing?: boolean;
	isPlaying?: boolean;
	viewMode?: "grid" | "list";
}

export default function VideoCard({
	video,
	onCategorize,
	onPlay,
	isCategorizing,
	isPlaying = false,
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
	const hasMiniPlayerAction = Boolean(onPlay && video.youtube_id);
	const handlePrimaryAction = () => {
		if (hasMiniPlayerAction && onPlay) {
			onPlay(video);
			return;
		}
		openYouTube();
	};

	// List view
	if (viewMode === "list") {
		return (
			<Card className="w-full hover:bg-surface-elevated transition-colors border border-border bg-surface shadow-none">
				<CardBody className="p-3 sm:p-4">
					<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-4">
						{/* biome-ignore lint/a11y/useSemanticElements: Using div with role="button" for layout flexibility */}
						<div
							role="button"
							tabIndex={0}
							className="flex-1 min-w-0 cursor-pointer w-full"
							onClick={handlePrimaryAction}
							onKeyDown={(e) => {
								if (e.key === "Enter" || e.key === " ") {
									e.preventDefault();
									handlePrimaryAction();
								}
							}}
						>
							<h3 className="font-semibold text-sm sm:text-base line-clamp-2 sm:line-clamp-1 mb-1 text-text-primary">
								{video.title}
							</h3>
							<div className="flex items-center flex-wrap gap-2 sm:gap-3 text-xs sm:text-sm text-text-secondary">
								<span className="truncate">{video.channel_title}</span>
								{video.duration_seconds && (
									<>
										<span>•</span>
										<span className="font-mono-editorial">
											{formatDuration(video.duration_seconds)}
										</span>
									</>
								)}
								{video.view_count && (
									<>
										<span>•</span>
										<span className="font-mono-editorial">
											{formatViews(video.view_count)} views
										</span>
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
											className="bg-[#E63946]/10 text-[#E63946]"
										>
											{category.name}
										</Chip>
									))}
									{video.tags.slice(0, 2).map((tag) => (
										<Chip
											key={tag.id}
											size="sm"
											className="bg-[#1E1E2A] text-[#6B6B7E]"
										>
											{tag.name}
										</Chip>
									))}
									{(video.categories.length > 2 || video.tags.length > 2) && (
										<Chip size="sm" className="bg-[#1E1E2A] text-[#6B6B7E]">
											+{video.categories.length + video.tags.length - 4}
										</Chip>
									)}
								</div>
							) : (
								<>
									<Chip size="sm" className="bg-[#F59E0B]/10 text-[#F59E0B]">
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

	// Grid view
	return (
		<Card
			className={`w-full bg-[#0F0F14] border ${
				isPlaying
					? "border-[#E63946] ring-1 ring-[#E63946]"
					: "border-[#1E1E2A] hover:border-[#2A2A38]"
			} group overflow-hidden shadow-none transition-colors`}
		>
			<CardBody className="p-0">
				{hasMiniPlayerAction ? (
					/* biome-ignore lint/a11y/useSemanticElements: Using div with role="button" for layout flexibility */
					<div
						role="button"
						tabIndex={0}
						className="relative cursor-pointer overflow-hidden"
						onClick={handlePrimaryAction}
						onKeyDown={(e) => {
							if (e.key === "Enter" || e.key === " ") {
								e.preventDefault();
								handlePrimaryAction();
							}
						}}
					>
						<Image
							shadow="none"
							radius="none"
							width="100%"
							alt={video.title}
							className="w-full object-cover h-[160px] sm:h-[200px] group-hover:scale-105 transition-transform duration-300"
							src={video.thumbnail_url || "/placeholder-thumbnail.jpg"}
						/>
						{/* Play overlay */}
						<div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/30">
							<div className="w-12 h-12 rounded-full bg-[#E63946] flex items-center justify-center shadow-lg">
								<PlayArrowIcon sx={{ fontSize: 28, color: "white" }} />
							</div>
						</div>
						{video.duration_seconds && (
							<div className="absolute bottom-2 right-2 glass-dark text-[#F2F2F7] font-mono-editorial text-xs px-2 py-1 rounded-md">
								{formatDuration(video.duration_seconds)}
							</div>
						)}
					</div>
				) : video.youtube_id ? (
					// Embedded player
					<div className="relative overflow-hidden">
						<div className="w-full object-cover h-[160px] sm:h-[200px]">
							<YouTubeEmbed videoid={video.youtube_id} height={200} />
						</div>
						{video.duration_seconds && (
							<div className="absolute bottom-2 right-2 glass-dark text-[#F2F2F7] font-mono-editorial text-xs px-2 py-1 rounded-md">
								{formatDuration(video.duration_seconds)}
							</div>
						)}
					</div>
				) : (
					/* biome-ignore lint/a11y/useSemanticElements: Using div with role="button" for layout flexibility */
					<div
						role="button"
						tabIndex={0}
						className="relative cursor-pointer overflow-hidden"
						onClick={openYouTube}
						onKeyDown={(e) => {
							if (e.key === "Enter" || e.key === " ") {
								e.preventDefault();
								openYouTube();
							}
						}}
					>
						<Image
							shadow="none"
							radius="none"
							width="100%"
							alt={video.title}
							className="w-full object-cover h-[160px] sm:h-[200px] group-hover:scale-105 transition-transform duration-300"
							src={video.thumbnail_url || "/placeholder-thumbnail.jpg"}
						/>
						{/* Play overlay */}
						<div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/30">
							<div className="w-12 h-12 rounded-full bg-[#E63946] flex items-center justify-center shadow-lg">
								<PlayArrowIcon sx={{ fontSize: 28, color: "white" }} />
							</div>
						</div>
						{video.duration_seconds && (
							<div className="absolute bottom-2 right-2 glass-dark text-[#F2F2F7] font-mono-editorial text-xs px-2 py-1 rounded-md">
								{formatDuration(video.duration_seconds)}
							</div>
						)}
					</div>
				)}
				{/* biome-ignore lint/a11y/useSemanticElements: Using div with role="button" for layout flexibility with nested interactive elements */}
				<div
					role="button"
					tabIndex={0}
					className="p-2 sm:p-3 space-y-1 sm:space-y-2 cursor-pointer"
					onClick={handlePrimaryAction}
					onKeyDown={(e) => {
						if (e.key === "Enter" || e.key === " ") {
							e.preventDefault();
							handlePrimaryAction();
						}
					}}
				>
					<Tooltip content={video.title}>
						<h3 className="font-semibold text-xs sm:text-sm line-clamp-2 text-[#F2F2F7]">
							{video.title}
						</h3>
					</Tooltip>
					<p className="text-xs text-[#6B6B7E] truncate">
						{video.channel_title}
					</p>
					<div className="flex items-center gap-1 sm:gap-2 text-xs text-[#6B6B7E] flex-wrap font-mono-editorial">
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
			<CardFooter className="flex-col items-start gap-2 pt-0 px-2 sm:px-3 pb-2 sm:pb-3">
				{video.is_categorized ? (
					<div className="flex flex-wrap gap-1 w-full">
						{video.categories.slice(0, 3).map((category) => (
							<Chip
								key={category.id}
								size="sm"
								className="bg-[#E63946]/10 text-[#E63946]"
							>
								{category.name}
							</Chip>
						))}
						{video.tags.slice(0, 2).map((tag) => (
							<Chip
								key={tag.id}
								size="sm"
								className="bg-[#1E1E2A] text-[#6B6B7E]"
							>
								{tag.name}
							</Chip>
						))}
						{(video.categories.length > 3 || video.tags.length > 2) && (
							<Chip size="sm" className="bg-[#1E1E2A] text-[#6B6B7E]">
								+{video.categories.length + video.tags.length - 5} more
							</Chip>
						)}
					</div>
				) : (
					<div className="flex items-center justify-between w-full">
						<Chip size="sm" className="bg-[#F59E0B]/10 text-[#F59E0B]">
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
				{hasMiniPlayerAction && (
					<Button
						size="sm"
						color="primary"
						variant="flat"
						className="w-full"
						startContent={<PlayArrowIcon fontSize="small" />}
						onPress={handlePrimaryAction}
					>
						{isPlaying ? "Playing in Mini Player" : "Play in Mini Player"}
					</Button>
				)}
			</CardFooter>
		</Card>
	);
}
