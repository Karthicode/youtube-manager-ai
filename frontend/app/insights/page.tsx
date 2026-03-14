"use client";

import { Spinner } from "@heroui/react";
import {
	CategoryPieChart,
	ChannelBarChart,
	ChannelRecommendations,
	DurationDistribution,
	InsightsSummaryCards,
	LikesTrendChart,
	TagCloud,
	TasteProfile,
} from "@/components/insights";
import Navbar from "@/components/Navbar";
import { useAuthGuard } from "@/hooks";
import {
	useInsightsChannels,
	useInsightsContentDist,
	useInsightsDuration,
	useInsightsOverview,
	useInsightsRecommendations,
	useInsightsTemporal,
} from "@/hooks/useInsights";

export default function InsightsPage() {
	const { isReady, isAuthenticated } = useAuthGuard();

	const { data: overview, isLoading: loadingOverview } = useInsightsOverview();
	const {
		categories,
		tags,
		isLoading: loadingContent,
		error: errContent,
	} = useInsightsContentDist();
	const {
		channels,
		isLoading: loadingChannels,
		error: errChannels,
	} = useInsightsChannels(10);
	const {
		temporal,
		isLoading: loadingTemporal,
		error: errTemporal,
	} = useInsightsTemporal();
	const {
		buckets,
		avgDuration,
		isLoading: loadingDuration,
		error: errDuration,
	} = useInsightsDuration();
	const {
		items: recommendations,
		topCategories,
		topTags,
		totalAnalyzed,
		isLoading: loadingRecommendations,
		error: errRecommendations,
	} = useInsightsRecommendations(10);

	// Don't render anything until hydrated and authenticated
	if (!isReady || !isAuthenticated) {
		return (
			<div className="min-h-screen bg-background flex justify-center items-center">
				<Spinner size="lg" color="primary" />
			</div>
		);
	}

	return (
		<div className="min-h-screen bg-background">
			<Navbar />
			<div className="container mx-auto px-4 sm:px-6 py-6 sm:py-8 max-w-7xl">
				<div className="space-y-6">
					{/* Header */}
					<div>
						<h1 className="font-display text-2xl sm:text-3xl font-bold text-text-primary tracking-tight">
							Insights
						</h1>
						<p className="text-sm sm:text-base text-text-secondary mt-1">
							Discover patterns in your liked videos
						</p>
					</div>

					{/* Summary Cards */}
					<InsightsSummaryCards data={overview} loading={loadingOverview} />

					{/* Charts Row 1: Category + Tags */}
					<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
						<CategoryPieChart
							data={categories}
							totalVideos={overview?.total_videos}
							loading={loadingContent}
							error={errContent?.message ?? ""}
						/>
						<TagCloud
							data={tags}
							loading={loadingContent}
							error={errContent?.message ?? ""}
						/>
					</div>

					{/* Charts Row 2: Likes Trend (Full Width) */}
					<LikesTrendChart
						data={temporal}
						loading={loadingTemporal}
						error={errTemporal?.message ?? ""}
					/>

					{/* Charts Row 3: Channels + Duration */}
					<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
						<ChannelBarChart
							data={channels}
							loading={loadingChannels}
							error={errChannels?.message ?? ""}
						/>
						<DurationDistribution
							data={buckets}
							avgDuration={avgDuration}
							loading={loadingDuration}
							error={errDuration?.message ?? ""}
						/>
					</div>

					{/* Channel Recommendations */}
					<ChannelRecommendations
						recommendations={recommendations}
						topCategories={topCategories}
						topTags={topTags}
						totalAnalyzed={totalAnalyzed}
						loading={loadingRecommendations}
						error={errRecommendations?.message ?? ""}
					/>

					{/* AI Taste Profile */}
					<TasteProfile />
				</div>
			</div>
		</div>
	);
}
