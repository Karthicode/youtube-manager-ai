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
	const words: WordData[] = data.map((tag) => ({
		text: tag.name,
		value: tag.count,
	}));

	const fontScale = scaleLog({
		domain: [
			Math.min(...data.map((d) => d.count), 1),
			Math.max(...data.map((d) => d.count), 1),
		],
		range: [12, 36],
	});

	const fontSizeSetter = (datum: WordData) => fontScale(datum.value);

	return (
		<ChartWrapper
			title="Tag Cloud"
			subtitle={`${data.length} tags`}
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
					padding={2}
					spiral="archimedean"
					rotate={0}
					random={() => 0.5}
				>
					{(cloudWords: WordcloudWord[]) => (
						<svg width={width} height={height}>
							<g transform={`translate(${width / 2},${height / 2})`}>
								{cloudWords.map((w: WordcloudWord, i: number) => (
									<Text
										key={w.text}
										fill={colors[i % colors.length]}
										textAnchor="middle"
										transform={`translate(${w.x}, ${w.y}) rotate(${w.rotate})`}
										fontSize={w.size}
										fontFamily={w.font}
										className="cursor-pointer transition-opacity hover:opacity-70"
									>
										{w.text}
									</Text>
								))}
							</g>
						</svg>
					)}
				</Wordcloud>
			)}
		</ChartWrapper>
	);
}
