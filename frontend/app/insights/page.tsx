"use client";

import { Spinner } from "@heroui/react";
import { useEffect, useState } from "react";
import { insightsApi } from "@/api/api";
import {
	CategoryPieChart,
	ChannelBarChart,
	ChannelRecommendations,
	DurationDistribution,
	InsightsSummaryCards,
	LikesTrendChart,
	TagCloud,
} from "@/components/insights";
import Navbar from "@/components/Navbar";
import { useAuthGuard } from "@/hooks";
import type {
	CategoryDistribution,
	ChannelRecommendation,
	ChannelStats,
	DurationBucket,
	InsightsOverview,
	TagDistribution,
	TemporalData,
} from "@/types";

export default function InsightsPage() {
	const { isReady, isAuthenticated } = useAuthGuard();

	// State for each data type
	const [overview, setOverview] = useState<InsightsOverview | null>(null);
	const [categories, setCategories] = useState<CategoryDistribution[]>([]);
	const [tags, setTags] = useState<TagDistribution[]>([]);
	const [channels, setChannels] = useState<ChannelStats[]>([]);
	const [temporal, setTemporal] = useState<TemporalData[]>([]);
	const [duration, setDuration] = useState<{
		buckets: DurationBucket[];
		avgDuration: number;
	}>({ buckets: [], avgDuration: 0 });
	const [recommendations, setRecommendations] = useState<{
		items: ChannelRecommendation[];
		topCategories: string[];
		topTags: string[];
		totalAnalyzed: number;
	}>({ items: [], topCategories: [], topTags: [], totalAnalyzed: 0 });

	// Loading and error states
	const [loading, setLoading] = useState({
		overview: true,
		content: true,
		channels: true,
		temporal: true,
		duration: true,
		recommendations: true,
	});
	const [errors, setErrors] = useState({
		overview: "",
		content: "",
		channels: "",
		temporal: "",
		duration: "",
		recommendations: "",
	});

	useEffect(() => {
		if (!isReady || !isAuthenticated) return;

		// Fetch all data in parallel
		const fetchData = async () => {
			// Fetch overview
			insightsApi
				.getOverview()
				.then((res) => {
					setOverview(res.data);
					setLoading((prev) => ({ ...prev, overview: false }));
				})
				.catch((err) => {
					setErrors((prev) => ({
						...prev,
						overview: err.response?.data?.detail || "Failed to load overview",
					}));
					setLoading((prev) => ({ ...prev, overview: false }));
				});

			// Fetch content distribution (categories & tags)
			insightsApi
				.getContentDistribution()
				.then((res) => {
					setCategories(res.data.categories || []);
					setTags(res.data.tags || []);
					setLoading((prev) => ({ ...prev, content: false }));
				})
				.catch((err) => {
					setErrors((prev) => ({
						...prev,
						content:
							err.response?.data?.detail ||
							"Failed to load content distribution",
					}));
					setLoading((prev) => ({ ...prev, content: false }));
				});

			// Fetch top channels
			insightsApi
				.getChannels({ limit: 10 })
				.then((res) => {
					setChannels(res.data.channels || []);
					setLoading((prev) => ({ ...prev, channels: false }));
				})
				.catch((err) => {
					setErrors((prev) => ({
						...prev,
						channels: err.response?.data?.detail || "Failed to load channels",
					}));
					setLoading((prev) => ({ ...prev, channels: false }));
				});

			// Fetch temporal data
			insightsApi
				.getTemporal()
				.then((res) => {
					setTemporal(res.data.by_month || []);
					setLoading((prev) => ({ ...prev, temporal: false }));
				})
				.catch((err) => {
					setErrors((prev) => ({
						...prev,
						temporal:
							err.response?.data?.detail || "Failed to load temporal data",
					}));
					setLoading((prev) => ({ ...prev, temporal: false }));
				});

			// Fetch duration data
			insightsApi
				.getDuration()
				.then((res) => {
					setDuration({
						buckets: res.data.buckets || [],
						avgDuration: res.data.avg_duration_seconds || 0,
					});
					setLoading((prev) => ({ ...prev, duration: false }));
				})
				.catch((err) => {
					setErrors((prev) => ({
						...prev,
						duration:
							err.response?.data?.detail || "Failed to load duration data",
					}));
					setLoading((prev) => ({ ...prev, duration: false }));
				});

			// Fetch recommendations
			insightsApi
				.getRecommendations({ limit: 10 })
				.then((res) => {
					setRecommendations({
						items: res.data.recommendations || [],
						topCategories: res.data.top_categories || [],
						topTags: res.data.top_tags || [],
						totalAnalyzed: res.data.total_analyzed_channels || 0,
					});
					setLoading((prev) => ({ ...prev, recommendations: false }));
				})
				.catch((err) => {
					setErrors((prev) => ({
						...prev,
						recommendations:
							err.response?.data?.detail || "Failed to load recommendations",
					}));
					setLoading((prev) => ({ ...prev, recommendations: false }));
				});
		};

		fetchData();
	}, [isReady, isAuthenticated]);

	// Don't render anything until hydrated and authenticated
	if (!isReady || !isAuthenticated) {
		return (
			<div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex justify-center items-center">
				<Spinner size="lg" />
			</div>
		);
	}

	return (
		<div className="min-h-screen bg-gray-50 dark:bg-gray-900">
			<Navbar />
			<div className="container mx-auto px-4 sm:px-6 py-6 sm:py-8 max-w-7xl">
				<div className="space-y-6">
					{/* Header */}
					<div>
						<h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white">
							Insights
						</h1>
						<p className="text-sm sm:text-base text-gray-600 dark:text-gray-400 mt-1">
							Discover patterns in your liked videos
						</p>
					</div>

					{/* Summary Cards */}
					<InsightsSummaryCards data={overview} loading={loading.overview} />

					{/* Charts Row 1: Category + Tags */}
					<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
						<CategoryPieChart
							data={categories}
							loading={loading.content}
							error={errors.content}
						/>
						<TagCloud
							data={tags}
							loading={loading.content}
							error={errors.content}
						/>
					</div>

					{/* Charts Row 2: Likes Trend (Full Width) */}
					<LikesTrendChart
						data={temporal}
						loading={loading.temporal}
						error={errors.temporal}
					/>

					{/* Charts Row 3: Channels + Duration */}
					<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
						<ChannelBarChart
							data={channels}
							loading={loading.channels}
							error={errors.channels}
						/>
						<DurationDistribution
							data={duration.buckets}
							avgDuration={duration.avgDuration}
							loading={loading.duration}
							error={errors.duration}
						/>
					</div>

					{/* Channel Recommendations */}
					<ChannelRecommendations
						recommendations={recommendations.items}
						topCategories={recommendations.topCategories}
						topTags={recommendations.topTags}
						totalAnalyzed={recommendations.totalAnalyzed}
						loading={loading.recommendations}
						error={errors.recommendations}
					/>
				</div>
			</div>
		</div>
	);
}
