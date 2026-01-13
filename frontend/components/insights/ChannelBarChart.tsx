"use client";

import { Group } from "@visx/group";
import { Bar } from "@visx/shape";
import { scaleLinear, scaleBand } from "@visx/scale";
import { AxisLeft } from "@visx/axis";
import { useTooltip, TooltipWithBounds } from "@visx/tooltip";
import { localPoint } from "@visx/event";
import type { ChannelStats } from "@/types";
import ChartWrapper from "./ChartWrapper";

interface ChannelBarChartProps {
	data: ChannelStats[];
	loading?: boolean;
	error?: string;
}

interface TooltipData {
	channel_title: string;
	video_count: number;
	total_views: number;
	avg_duration_seconds: number;
}

function formatViews(views: number): string {
	if (views >= 1_000_000) return `${(views / 1_000_000).toFixed(1)}M`;
	if (views >= 1_000) return `${(views / 1_000).toFixed(1)}K`;
	return views.toString();
}

function truncateText(text: string, maxLength: number): string {
	if (text.length <= maxLength) return text;
	return `${text.slice(0, maxLength - 3)}...`;
}

export default function ChannelBarChart({
	data,
	loading = false,
	error,
}: ChannelBarChartProps) {
	const {
		tooltipOpen,
		tooltipData,
		tooltipLeft,
		tooltipTop,
		showTooltip,
		hideTooltip,
	} = useTooltip<TooltipData>();

	const margin = { top: 10, right: 20, bottom: 10, left: 120 };

	return (
		<>
			<ChartWrapper
				title="Top Channels"
				subtitle={`${data.length} channels by liked videos`}
				loading={loading}
				error={error}
				height="h-[350px]"
			>
				{({ width, height }) => {
					const xMax = Math.max(0, width - margin.left - margin.right);
					const yMax = Math.max(0, height - margin.top - margin.bottom);

					// Don't render if dimensions are too small
					if (xMax < 10 || yMax < 10) {
						return <svg width={width} height={height} />;
					}

					const xScale = scaleLinear<number>({
						domain: [0, Math.max(...data.map((d) => d.video_count), 1)],
						range: [0, xMax],
						nice: true,
					});

					const yScale = scaleBand<string>({
						domain: data.map((d) => d.channel_title),
						range: [0, yMax],
						padding: 0.3,
					});

					return (
						<svg width={width} height={height}>
							<Group left={margin.left} top={margin.top}>
								<AxisLeft
									scale={yScale}
									stroke="transparent"
									tickStroke="transparent"
									tickFormat={(value) => truncateText(value, 15)}
									tickLabelProps={() => ({
										fill: "currentColor",
										fontSize: 11,
										textAnchor: "end",
										dy: "0.33em",
										className: "text-gray-600 dark:text-gray-400",
									})}
								/>
								{data.map((d) => {
									const barHeight = yScale.bandwidth();
									const barWidth = xScale(d.video_count);
									const barY = yScale(d.channel_title) || 0;

									return (
										<g
											key={d.channel_id}
											onMouseMove={(event) => {
												const coords = localPoint(event);
												showTooltip({
													tooltipData: d,
													tooltipLeft: (coords?.x || 0) + margin.left,
													tooltipTop: (coords?.y || 0) + margin.top,
												});
											}}
											onMouseLeave={hideTooltip}
										>
											<Bar
												x={0}
												y={barY}
												width={barWidth}
												height={barHeight}
												rx={4}
												className="fill-blue-500 hover:fill-blue-400 transition-colors cursor-pointer"
											/>
											<text
												x={barWidth + 5}
												y={barY + barHeight / 2}
												dy=".33em"
												fontSize={11}
												className="fill-gray-600 dark:fill-gray-400 font-medium"
											>
												{d.video_count}
											</text>
										</g>
									);
								})}
							</Group>
						</svg>
					);
				}}
			</ChartWrapper>

			{tooltipOpen && tooltipData && (
				<TooltipWithBounds
					top={tooltipTop}
					left={tooltipLeft}
					className="!bg-white dark:!bg-gray-800 !shadow-lg !rounded-lg !px-3 !py-2 !border !border-gray-200 dark:!border-gray-700"
				>
					<div className="text-sm space-y-1">
						<p className="font-semibold text-gray-800 dark:text-gray-200">
							{tooltipData.channel_title}
						</p>
						<p className="text-gray-600 dark:text-gray-400">
							{tooltipData.video_count} videos liked
						</p>
						<p className="text-gray-600 dark:text-gray-400">
							{formatViews(tooltipData.total_views)} total views
						</p>
					</div>
				</TooltipWithBounds>
			)}
		</>
	);
}
