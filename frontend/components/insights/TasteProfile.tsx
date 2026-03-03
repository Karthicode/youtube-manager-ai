"use client";

import {
	Button,
	Card,
	CardBody,
	CardHeader,
	Chip,
	Spinner,
	Tooltip,
} from "@heroui/react";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import TrendingDownIcon from "@mui/icons-material/TrendingDown";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import { useCallback, useEffect, useState } from "react";
import { insightsApi } from "@/api/api";
import type { TasteProfileResponse } from "@/types";

export default function TasteProfile() {
	const [data, setData] = useState<TasteProfileResponse | null>(null);
	const [loading, setLoading] = useState(true);
	const [generating, setGenerating] = useState(false);
	const [error, setError] = useState("");

	const fetchProfile = useCallback(async () => {
		try {
			setLoading(true);
			const res = await insightsApi.getTasteProfile();
			setData(res.data);
			if (res.data.status === "generating") {
				setGenerating(true);
			} else {
				setGenerating(false);
			}
		} catch (err: unknown) {
			const axiosErr = err as { response?: { data?: { detail?: string } } };
			setError(
				axiosErr.response?.data?.detail || "Failed to load taste profile",
			);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		fetchProfile();
	}, [fetchProfile]);

	// Poll while generating
	useEffect(() => {
		if (!generating) return;
		const interval = setInterval(async () => {
			try {
				const res = await insightsApi.getTasteProfile();
				setData(res.data);
				if (res.data.status !== "generating") {
					setGenerating(false);
				}
			} catch {
				// ignore polling errors
			}
		}, 5000);
		return () => clearInterval(interval);
	}, [generating]);

	const handleGenerate = async () => {
		try {
			setGenerating(true);
			setError("");
			await insightsApi.generateTasteProfile();
			// Start polling
			setTimeout(fetchProfile, 3000);
		} catch (err: unknown) {
			const axiosErr = err as { response?: { data?: { detail?: string } } };
			setError(axiosErr.response?.data?.detail || "Failed to generate profile");
			setGenerating(false);
		}
	};

	if (loading) {
		return (
			<Card className="shadow-lg">
				<CardBody className="h-[200px] flex items-center justify-center">
					<Spinner size="lg" />
				</CardBody>
			</Card>
		);
	}

	if (error) {
		return (
			<Card className="shadow-lg">
				<CardBody className="h-[200px] flex items-center justify-center">
					<p className="text-red-500 text-sm">{error}</p>
				</CardBody>
			</Card>
		);
	}

	// Not available or not enough videos
	if (!data || data.status === "not_available" || !data.profile) {
		return (
			<Card className="shadow-lg">
				<CardHeader className="pb-2">
					<div className="flex items-center gap-2">
						<AutoAwesomeIcon className="text-primary" />
						<h3 className="text-base sm:text-lg font-semibold">
							AI Taste Profile
						</h3>
					</div>
				</CardHeader>
				<CardBody>
					<div className="flex flex-col items-center justify-center py-8 text-center">
						<AutoAwesomeIcon
							className="text-gray-400 mb-3"
							sx={{ fontSize: 48 }}
						/>
						{data && data.video_count < data.min_videos_required ? (
							<>
								<p className="text-sm text-gray-600 dark:text-gray-400">
									Need at least {data.min_videos_required} videos with
									embeddings to generate a taste profile.
								</p>
								<p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
									You currently have {data.video_count} videos.
								</p>
							</>
						) : (
							<>
								<p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
									Generate an AI-powered analysis of your viewing patterns,
									interests, and how your taste has evolved over time.
								</p>
								<Button
									color="primary"
									onPress={handleGenerate}
									isLoading={generating}
								>
									{generating ? "Generating..." : "Generate Taste Profile"}
								</Button>
							</>
						)}
					</div>
				</CardBody>
			</Card>
		);
	}

	// Generating state
	if (data.status === "generating") {
		return (
			<Card className="shadow-lg">
				<CardHeader className="pb-2">
					<div className="flex items-center gap-2">
						<AutoAwesomeIcon className="text-primary" />
						<h3 className="text-base sm:text-lg font-semibold">
							AI Taste Profile
						</h3>
					</div>
				</CardHeader>
				<CardBody>
					<div className="flex flex-col items-center justify-center py-8">
						<Spinner size="lg" className="mb-3" />
						<p className="text-sm text-gray-600 dark:text-gray-400">
							Analyzing your video library...
						</p>
						<p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
							This may take a minute for large libraries
						</p>
					</div>
				</CardBody>
			</Card>
		);
	}

	const { profile } = data;

	return (
		<div className="space-y-6">
			{/* Identity Summary */}
			<Card className="shadow-lg">
				<CardHeader className="pb-2">
					<div className="flex items-center justify-between w-full">
						<div className="flex items-center gap-2">
							<AutoAwesomeIcon className="text-primary" />
							<h3 className="text-base sm:text-lg font-semibold">
								AI Taste Profile
							</h3>
						</div>
						<Button
							size="sm"
							variant="flat"
							color="primary"
							onPress={handleGenerate}
							isLoading={generating}
						>
							Regenerate
						</Button>
					</div>
				</CardHeader>
				<CardBody>
					<p className="text-sm sm:text-base text-gray-700 dark:text-gray-300 leading-relaxed">
						{profile.identity_summary}
					</p>
					{profile.personality_tags.length > 0 && (
						<div className="flex flex-wrap gap-2 mt-4">
							{profile.personality_tags.map((tag) => (
								<Chip
									key={tag}
									size="sm"
									color="secondary"
									variant="flat"
									className="capitalize"
								>
									{tag}
								</Chip>
							))}
						</div>
					)}
				</CardBody>
			</Card>

			{/* Interest Clusters */}
			<div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
				{/* Primary Interests */}
				{profile.primary_interests.length > 0 && (
					<Card className="shadow-lg">
						<CardHeader className="pb-1">
							<h4 className="text-sm font-semibold text-gray-900 dark:text-white">
								Primary Interests
							</h4>
						</CardHeader>
						<CardBody className="pt-1">
							<div className="space-y-3">
								{profile.primary_interests.map((cluster) => (
									<div key={cluster.label}>
										<div className="flex items-center justify-between mb-1">
											<span className="text-sm font-medium text-gray-700 dark:text-gray-300">
												{cluster.label}
											</span>
											<span className="text-xs font-semibold text-primary">
												{Math.round(cluster.percentage)}%
											</span>
										</div>
										<div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
											<div
												className="bg-primary rounded-full h-2 transition-all"
												style={{ width: `${cluster.percentage}%` }}
											/>
										</div>
										<p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
											{cluster.description}
										</p>
									</div>
								))}
							</div>
						</CardBody>
					</Card>
				)}

				{/* Emerging Interests */}
				{profile.emerging_interests.length > 0 && (
					<Card className="shadow-lg border-l-4 border-l-success">
						<CardHeader className="pb-1">
							<div className="flex items-center gap-2">
								<TrendingUpIcon
									className="text-success"
									sx={{ fontSize: 18 }}
								/>
								<h4 className="text-sm font-semibold text-gray-900 dark:text-white">
									Emerging Interests
								</h4>
							</div>
						</CardHeader>
						<CardBody className="pt-1">
							<div className="space-y-3">
								{profile.emerging_interests.map((cluster) => (
									<div key={cluster.label}>
										<div className="flex items-center justify-between mb-1">
											<span className="text-sm font-medium text-gray-700 dark:text-gray-300">
												{cluster.label}
											</span>
											<Chip size="sm" color="success" variant="flat">
												Rising
											</Chip>
										</div>
										<p className="text-xs text-gray-500 dark:text-gray-400">
											{cluster.description}
										</p>
									</div>
								))}
							</div>
						</CardBody>
					</Card>
				)}

				{/* Declining Interests */}
				{profile.declining_interests.length > 0 && (
					<Card className="shadow-lg border-l-4 border-l-warning">
						<CardHeader className="pb-1">
							<div className="flex items-center gap-2">
								<TrendingDownIcon
									className="text-warning"
									sx={{ fontSize: 18 }}
								/>
								<h4 className="text-sm font-semibold text-gray-900 dark:text-white">
									Declining Interests
								</h4>
							</div>
						</CardHeader>
						<CardBody className="pt-1">
							<div className="space-y-3">
								{profile.declining_interests.map((cluster) => (
									<div key={cluster.label}>
										<div className="flex items-center justify-between mb-1">
											<span className="text-sm font-medium text-gray-700 dark:text-gray-300">
												{cluster.label}
											</span>
											<Chip size="sm" color="warning" variant="flat">
												Fading
											</Chip>
										</div>
										<p className="text-xs text-gray-500 dark:text-gray-400">
											{cluster.description}
										</p>
									</div>
								))}
							</div>
						</CardBody>
					</Card>
				)}
			</div>

			{/* Consumption Style */}
			<Card className="shadow-lg">
				<CardHeader className="pb-2">
					<h4 className="text-sm font-semibold text-gray-900 dark:text-white">
						Consumption Style
					</h4>
				</CardHeader>
				<CardBody className="pt-1">
					<div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
						<div className="text-center p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20">
							<p className="text-xs text-gray-500 dark:text-gray-400 mb-1">
								Duration Preference
							</p>
							<p className="text-sm font-semibold text-blue-600 dark:text-blue-400 capitalize">
								{profile.consumption_style.avg_duration_preference}
							</p>
						</div>
						<div className="text-center p-3 rounded-lg bg-purple-50 dark:bg-purple-900/20">
							<p className="text-xs text-gray-500 dark:text-gray-400 mb-1">
								Channel Diversity
							</p>
							<p className="text-sm font-semibold text-purple-600 dark:text-purple-400 capitalize">
								{profile.consumption_style.channel_diversity}
							</p>
						</div>
						<div className="text-center p-3 rounded-lg bg-green-50 dark:bg-green-900/20">
							<p className="text-xs text-gray-500 dark:text-gray-400 mb-1">
								Content Depth
							</p>
							<p className="text-sm font-semibold text-green-600 dark:text-green-400 capitalize">
								{profile.consumption_style.content_depth}
							</p>
						</div>
						<div className="text-center p-3 rounded-lg bg-orange-50 dark:bg-orange-900/20">
							<p className="text-xs text-gray-500 dark:text-gray-400 mb-1">
								Viewing Pattern
							</p>
							<Tooltip content={profile.consumption_style.viewing_pattern}>
								<p className="text-sm font-semibold text-orange-600 dark:text-orange-400 capitalize truncate">
									{profile.consumption_style.viewing_pattern}
								</p>
							</Tooltip>
						</div>
					</div>
				</CardBody>
			</Card>

			{/* Interest Drift Timeline */}
			{profile.drift_events.length > 0 && (
				<Card className="shadow-lg">
					<CardHeader className="pb-2">
						<h4 className="text-sm font-semibold text-gray-900 dark:text-white">
							Interest Drift Timeline
						</h4>
					</CardHeader>
					<CardBody className="pt-1">
						<div className="relative">
							{/* Timeline line */}
							<div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-200 dark:bg-gray-700" />

							<div className="space-y-6">
								{profile.drift_events.map((event, index) => {
									const intensity =
										event.magnitude > 0.3
											? "high"
											: event.magnitude > 0.2
												? "medium"
												: "low";
									const dotColor =
										intensity === "high"
											? "bg-red-500"
											: intensity === "medium"
												? "bg-yellow-500"
												: "bg-blue-500";

									return (
										<div
											key={`${event.period}-${index}`}
											className="relative pl-10"
										>
											{/* Timeline dot */}
											<div
												className={`absolute left-2.5 top-1 w-3 h-3 rounded-full ${dotColor} ring-2 ring-white dark:ring-gray-900`}
											/>

											<div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
												<p className="text-xs text-gray-500 dark:text-gray-400 mb-1">
													{event.period}
												</p>
												<div className="flex items-center gap-2 flex-wrap">
													<Chip size="sm" variant="flat" color="default">
														{event.from_interest}
													</Chip>
													<ArrowForwardIcon
														className="text-gray-400"
														sx={{ fontSize: 16 }}
													/>
													<Chip size="sm" variant="flat" color="primary">
														{event.to_interest}
													</Chip>
													<Chip
														size="sm"
														variant="dot"
														color={
															intensity === "high"
																? "danger"
																: intensity === "medium"
																	? "warning"
																	: "primary"
														}
													>
														{intensity} shift
													</Chip>
												</div>
											</div>
										</div>
									);
								})}
							</div>
						</div>
					</CardBody>
				</Card>
			)}
		</div>
	);
}
