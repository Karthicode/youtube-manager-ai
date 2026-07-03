"use client";

import { Spinner } from "@heroui/react";
import {
	CategoryPieChart,
	ChannelBarChart,
	DurationDistribution,
	InsightsSummaryCards,
	LikesTrendChart,
	TasteProfile,
} from "@/components/insights";
import Navbar from "@/components/Navbar";
import { useAuthGuard } from "@/hooks";
import {
	useInsightsChannels,
	useInsightsContentDist,
	useInsightsDuration,
	useInsightsOverview,
	useInsightsTemporal,
} from "@/hooks/useInsights";

function SectionLabel({ children }: { children: React.ReactNode }) {
	return (
		<h2 className="text-[11px] uppercase tracking-widest text-text-secondary font-semibold">
			{children}
		</h2>
	);
}

export default function InsightsPage() {
	const { isReady, isAuthenticated } = useAuthGuard();

	const { data: overview, isLoading: loadingOverview } = useInsightsOverview();
	const {
		categories,
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

					{/* Compact summary strip */}
					<InsightsSummaryCards data={overview} loading={loadingOverview} />

					{/* Taste Profile — marquee AI element */}
					<div className="space-y-3">
						<SectionLabel>Your taste profile</SectionLabel>
						<TasteProfile />
					</div>

					{/* What you watch / Who you watch */}
					<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
						<div className="space-y-3">
							<SectionLabel>What you watch</SectionLabel>
							<CategoryPieChart
								data={categories}
								totalVideos={overview?.total_videos}
								loading={loadingContent}
								error={errContent?.message ?? ""}
							/>
						</div>
						<div className="space-y-3">
							<SectionLabel>Who you watch</SectionLabel>
							<ChannelBarChart
								data={channels}
								loading={loadingChannels}
								error={errChannels?.message ?? ""}
							/>
						</div>
					</div>

					{/* How you watch */}
					<div className="space-y-3">
						<SectionLabel>How you watch</SectionLabel>
						<LikesTrendChart
							data={temporal}
							loading={loadingTemporal}
							error={errTemporal?.message ?? ""}
						/>
						<DurationDistribution
							data={buckets}
							avgDuration={avgDuration}
							loading={loadingDuration}
							error={errDuration?.message ?? ""}
						/>
					</div>
				</div>
			</div>
		</div>
	);
}
