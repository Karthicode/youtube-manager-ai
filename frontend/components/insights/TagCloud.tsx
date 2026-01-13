"use client";

import type { TagDistribution } from "@/types";
import ChartWrapper from "./ChartWrapper";

interface TagCloudProps {
	data: TagDistribution[];
	loading?: boolean;
	error?: string;
}

const colors = [
	"#3B82F6", "#8B5CF6", "#EC4899", "#F59E0B", "#22C55E",
	"#06B6D4", "#EF4444", "#6366F1", "#14B8A6", "#F97316",
];

export default function TagCloud({
	data,
	loading = false,
	error,
}: TagCloudProps) {
	// Limit to top 30 tags for better layout
	const limitedData = data.slice(0, 30);

	if (limitedData.length === 0) {
		return (
			<ChartWrapper
				title="Tag Cloud"
				subtitle="0 tags"
				loading={loading}
				error={error}
				height="h-[280px]"
			>
				{() => (
					<div className="flex items-center justify-center h-full text-gray-500">
						No tags available
					</div>
				)}
			</ChartWrapper>
		);
	}

	// Calculate font sizes based on count
	const minCount = Math.min(...limitedData.map((d) => d.count));
	const maxCount = Math.max(...limitedData.map((d) => d.count));
	const range = maxCount - minCount || 1;

	const getFontSize = (count: number) => {
		const normalized = (count - minCount) / range;
		return Math.round(14 + normalized * 20); // 14px to 34px
	};

	return (
		<ChartWrapper
			title="Tag Cloud"
			subtitle={`${data.length} tags${data.length > 30 ? " (showing top 30)" : ""}`}
			loading={loading}
			error={error}
			height="h-[280px]"
		>
			{() => (
				<div className="flex flex-wrap items-center justify-center gap-2 p-4 h-full overflow-hidden">
					{limitedData.map((tag, i) => (
						<span
							key={tag.name}
							className="inline-block cursor-pointer transition-opacity hover:opacity-70 whitespace-nowrap"
							style={{
								fontSize: `${getFontSize(tag.count)}px`,
								color: colors[i % colors.length],
								lineHeight: 1.2,
							}}
							title={`${tag.name}: ${tag.count} videos`}
						>
							{tag.name}
						</span>
					))}
				</div>
			)}
		</ChartWrapper>
	);
}
