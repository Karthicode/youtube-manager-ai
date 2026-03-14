"use client";

import { localPoint } from "@visx/event";
import { Group } from "@visx/group";
import { scaleOrdinal } from "@visx/scale";
import { Pie } from "@visx/shape";
import { defaultStyles, TooltipWithBounds, useTooltip } from "@visx/tooltip";
import type { CategoryDistribution } from "@/types";
import ChartWrapper from "./ChartWrapper";

// Default color palette for categories
const defaultColors = [
	"#3B82F6",
	"#EF4444",
	"#22C55E",
	"#F59E0B",
	"#8B5CF6",
	"#EC4899",
	"#06B6D4",
	"#F97316",
	"#6366F1",
	"#14B8A6",
	"#D946EF",
	"#84CC16",
	"#0EA5E9",
	"#A855F7",
	"#F43F5E",
];

interface CategoryPieChartProps {
	data: CategoryDistribution[];
	totalVideos?: number;
	loading?: boolean;
	error?: string;
}

interface TooltipData {
	name: string;
	count: number;
	percentage: number;
}

export default function CategoryPieChart({
	data,
	totalVideos,
	loading = false,
	error,
}: CategoryPieChartProps) {
	const {
		tooltipOpen,
		tooltipData,
		tooltipLeft,
		tooltipTop,
		showTooltip,
		hideTooltip,
	} = useTooltip<TooltipData>();

	const colorScale = scaleOrdinal<string, string>({
		domain: data.map((d) => d.name),
		range: data.map(
			(d, i) => d.color || defaultColors[i % defaultColors.length],
		),
	});

	const total = totalVideos ?? data.reduce((sum, d) => sum + d.count, 0);

	return (
		<div className="relative">
			<ChartWrapper
				title="Category Distribution"
				subtitle={`${data.length} categories`}
				loading={loading}
				error={error}
				height="h-[280px]"
			>
				{({ width, height }) => {
					const radius = Math.max(0, Math.min(width, height) / 2 - 20);
					const innerRadius = radius * 0.6;
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
							aria-label="Category distribution pie chart"
						>
							<title>Category Distribution</title>
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
												arc.endAngle - arc.startAngle > 0.3;
											const arcPath = pie.path(arc) || "";
											const arcFill = colorScale(arc.data.name);

											return (
												/* biome-ignore lint/a11y/useSemanticElements: SVG g element cannot be replaced with button */
												<g
													key={`arc-${arc.data.name}`}
													role="button"
													tabIndex={0}
													onMouseMove={(event) => {
														const eventSvgCoords = localPoint(event);
														showTooltip({
															tooltipData: {
																name: arc.data.name,
																count: arc.data.count,
																percentage: arc.data.percentage,
															},
															tooltipLeft: (eventSvgCoords?.x || 0) + 10,
															tooltipTop: (eventSvgCoords?.y || 0) + 60,
														});
													}}
													onMouseLeave={hideTooltip}
													onFocus={() => {
														showTooltip({
															tooltipData: {
																name: arc.data.name,
																count: arc.data.count,
																percentage: arc.data.percentage,
															},
															tooltipLeft: 0,
															tooltipTop: 0,
														});
													}}
													onBlur={hideTooltip}
													style={{ cursor: "pointer" }}
													aria-label={`${arc.data.name}: ${arc.data.count} videos (${arc.data.percentage.toFixed(1)}%)`}
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
															fontSize={10}
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

			{tooltipOpen && tooltipData && (
				<TooltipWithBounds
					top={tooltipTop}
					left={tooltipLeft}
					style={{
						...defaultStyles,
						backgroundColor: "var(--tooltip-bg, white)",
						color: "var(--tooltip-text, #1f2937)",
						padding: "8px 12px",
						borderRadius: "8px",
						boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
						border: "1px solid var(--tooltip-border, #e5e7eb)",
					}}
				>
					<div className="text-sm">
						<p className="font-semibold">{tooltipData.name}</p>
						<p className="opacity-75">
							{tooltipData.count} videos ({tooltipData.percentage.toFixed(1)}%)
						</p>
					</div>
				</TooltipWithBounds>
			)}
		</div>
	);
}
