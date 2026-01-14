"use client";

import { localPoint } from "@visx/event";
import { Group } from "@visx/group";
import { scaleOrdinal } from "@visx/scale";
import { Pie } from "@visx/shape";
import { TooltipWithBounds, useTooltip } from "@visx/tooltip";
import type { DurationBucket } from "@/types";
import ChartWrapper from "./ChartWrapper";

interface DurationDistributionProps {
	data: DurationBucket[];
	avgDuration: number;
	loading?: boolean;
	error?: string;
}

const durationColors = {
	Short: "#22C55E",
	Medium: "#3B82F6",
	Long: "#F59E0B",
	"Very Long": "#EF4444",
};

function formatDuration(seconds: number): string {
	if (seconds < 60) return `${seconds}s`;
	if (seconds < 3600) {
		const mins = Math.floor(seconds / 60);
		const secs = seconds % 60;
		return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
	}
	const hours = Math.floor(seconds / 3600);
	const mins = Math.floor((seconds % 3600) / 60);
	return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
}

export default function DurationDistribution({
	data,
	avgDuration,
	loading = false,
	error,
}: DurationDistributionProps) {
	const {
		tooltipOpen,
		tooltipData,
		tooltipLeft,
		tooltipTop,
		showTooltip,
		hideTooltip,
	} = useTooltip<DurationBucket>();

	const colorScale = scaleOrdinal<string, string>({
		domain: data.map((d) => d.label),
		range: data.map(
			(d) =>
				durationColors[d.label as keyof typeof durationColors] || "#6B7280",
		),
	});

	const total = data.reduce((sum, d) => sum + d.count, 0);

	return (
		<>
			<ChartWrapper
				title="Duration Distribution"
				subtitle={`Avg: ${formatDuration(avgDuration)}`}
				loading={loading}
				error={error}
				height="h-[280px]"
			>
				{({ width, height }) => {
					const radius = Math.max(0, Math.min(width, height) / 2 - 20);
					const innerRadius = radius * 0.55;
					const centerX = width / 2;
					const centerY = height / 2;

					// Don't render if dimensions are too small
					if (radius < 10) {
						return <svg width={width} height={height} />;
					}

					return (
						<svg
							width={width}
							height={height}
							role="img"
							aria-label="Duration distribution pie chart"
						>
							<title>Video Duration Distribution</title>
							<Group top={centerY} left={centerX}>
								<Pie
									data={data}
									pieValue={(d) => d.count}
									outerRadius={radius}
									innerRadius={innerRadius}
									padAngle={0.02}
								>
									{(pie) =>
										pie.arcs.map((arc) => {
											const [centroidX, centroidY] = pie.path.centroid(arc);
											const hasSpaceForLabel =
												arc.endAngle - arc.startAngle > 0.4;
											const arcPath = pie.path(arc) || "";
											const arcFill = colorScale(arc.data.label);

											return (
												/* biome-ignore lint/a11y/useSemanticElements: SVG g element cannot be replaced with button */
												<g
													key={`arc-${arc.data.label}`}
													role="button"
													tabIndex={0}
													onMouseMove={(event) => {
														const coords = localPoint(event);
														showTooltip({
															tooltipData: arc.data,
															tooltipLeft: coords?.x,
															tooltipTop: coords?.y,
														});
													}}
													onMouseLeave={hideTooltip}
													onFocus={() => {
														showTooltip({
															tooltipData: arc.data,
															tooltipLeft: 0,
															tooltipTop: 0,
														});
													}}
													onBlur={hideTooltip}
													style={{ cursor: "pointer" }}
													aria-label={`${arc.data.label}: ${arc.data.count} videos (${arc.data.percentage.toFixed(1)}%)`}
												>
													<path
														d={arcPath}
														fill={arcFill}
														className="transition-opacity hover:opacity-80"
													/>
													{hasSpaceForLabel && (
														<text
															x={centroidX}
															y={centroidY}
															dy=".33em"
															fill="white"
															fontSize={11}
															textAnchor="middle"
															pointerEvents="none"
															className="font-medium"
														>
															{arc.data.percentage.toFixed(0)}%
														</text>
													)}
												</g>
											);
										})
									}
								</Pie>
								{/* Center text */}
								<text
									textAnchor="middle"
									dy="-0.2em"
									className="fill-gray-700 dark:fill-gray-200 text-lg font-bold"
								>
									{total}
								</text>
								<text
									textAnchor="middle"
									dy="1.2em"
									className="fill-gray-500 dark:fill-gray-400 text-xs"
								>
									videos
								</text>
							</Group>
						</svg>
					);
				}}
			</ChartWrapper>

			{/* Legend */}
			<div className="flex flex-wrap justify-center gap-3 mt-2 px-2">
				{data.map((bucket) => (
					<div key={bucket.label} className="flex items-center gap-1.5">
						<div
							className="w-3 h-3 rounded-full"
							style={{ backgroundColor: colorScale(bucket.label) }}
						/>
						<span className="text-xs text-gray-600 dark:text-gray-400">
							{bucket.label} ({bucket.range_label})
						</span>
					</div>
				))}
			</div>

			{tooltipOpen && tooltipData && (
				<TooltipWithBounds
					top={tooltipTop}
					left={tooltipLeft}
					className="!bg-white dark:!bg-gray-800 !shadow-lg !rounded-lg !px-3 !py-2 !border !border-gray-200 dark:!border-gray-700"
				>
					<div className="text-sm space-y-1">
						<p className="font-semibold text-gray-800 dark:text-gray-200">
							{tooltipData.label}
						</p>
						<p className="text-gray-600 dark:text-gray-400">
							{tooltipData.range_label}
						</p>
						<p className="text-gray-600 dark:text-gray-400">
							{tooltipData.count} videos ({tooltipData.percentage.toFixed(1)}%)
						</p>
					</div>
				</TooltipWithBounds>
			)}
		</>
	);
}
