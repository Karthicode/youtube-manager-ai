"use client";

import { Text } from "@visx/text";
import { scaleLog } from "@visx/scale";
import { Wordcloud } from "@visx/wordcloud";
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

interface WordData {
	text: string;
	value: number;
}

interface WordcloudWord {
	text?: string;
	x?: number;
	y?: number;
	rotate?: number;
	size?: number;
	font?: string;
}

export default function TagCloud({
	data,
	loading = false,
	error,
}: TagCloudProps) {
	// Limit to top 30 tags for better layout
	const limitedData = data.slice(0, 30);

	const words: WordData[] = limitedData.map((tag) => ({
		text: tag.name,
		value: tag.count,
	}));

	// Handle edge cases for font scale
	const minCount = Math.min(...limitedData.map((d) => d.count), 1);
	const maxCount = Math.max(...limitedData.map((d) => d.count), 1);

	const fontScale = scaleLog({
		domain: [minCount, Math.max(maxCount, minCount + 1)],
		range: [14, 32],
	});

	const fontSizeSetter = (datum: WordData) => fontScale(datum.value);

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

	return (
		<ChartWrapper
			title="Tag Cloud"
			subtitle={`${data.length} tags${data.length > 30 ? " (showing top 30)" : ""}`}
			loading={loading}
			error={error}
			height="h-[280px]"
		>
			{({ width, height }) => (
				<Wordcloud
					words={words}
					width={width}
					height={height}
					fontSize={fontSizeSetter}
					font="Inter, system-ui, sans-serif"
					padding={3}
					spiral="rectangular"
					rotate={0}
					random={() => 0.5}
				>
					{(cloudWords: WordcloudWord[]) => {
						// Calculate bounds to center the cloud
						const validWords = cloudWords.filter(w => w.x !== undefined && w.y !== undefined);

						if (validWords.length === 0) {
							return (
								<svg width={width} height={height}>
									<text
										x={width / 2}
										y={height / 2}
										textAnchor="middle"
										className="fill-gray-500"
									>
										Unable to render tags
									</text>
								</svg>
							);
						}

						return (
							<svg width={width} height={height}>
								<g transform={`translate(${width / 2},${height / 2})`}>
									{validWords.map((w: WordcloudWord, i: number) => (
										<Text
											key={`${w.text}-${i}`}
											fill={colors[i % colors.length]}
											textAnchor="middle"
											verticalAnchor="middle"
											x={w.x}
											y={w.y}
											fontSize={w.size}
											fontFamily={w.font}
											className="cursor-pointer transition-opacity hover:opacity-70"
										>
											{w.text}
										</Text>
									))}
								</g>
							</svg>
						);
					}}
				</Wordcloud>
			)}
		</ChartWrapper>
	);
}
