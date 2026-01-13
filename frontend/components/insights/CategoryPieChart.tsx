"use client";

import { Group } from "@visx/group";
import { Pie } from "@visx/shape";
import { scaleOrdinal } from "@visx/scale";
import { useTooltip, TooltipWithBounds } from "@visx/tooltip";
import { localPoint } from "@visx/event";
import type { CategoryDistribution } from "@/types";
import ChartWrapper from "./ChartWrapper";

// Default color palette for categories
const defaultColors = [
	"#3B82F6", "#EF4444", "#22C55E", "#F59E0B", "#8B5CF6",
	"#EC4899", "#06B6D4", "#F97316", "#6366F1", "#14B8A6",
	"#D946EF", "#84CC16", "#0EA5E9", "#A855F7", "#F43F5E",
];

interface CategoryPieChartProps {
	data: CategoryDistribution[];
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
		range: data.map((d, i) => d.color || defaultColors[i % defaultColors.length]),
	});

	const total = data.reduce((sum, d) => sum + d.count, 0);

	return (
		<>
			<ChartWrapper
				title="Category Distribution"
				subtitle={`${data.length} categories`}
				loading={loading}
				error={error}
				height="h-[280px]"
			>
				{({ width, height }) => {
					const radius = Math.min(width, height) / 2 - 20;
					const innerRadius = radius * 0.6;
					const centerX = width / 2;
					const centerY = height / 2;

					return (
						<svg width={width} height={height}>
							<Group top={centerY} left={centerX}>
								<Pie
									data={data}
									pieValue={(d) => d.count}
									outerRadius={radius}
									innerRadius={innerRadius}
									padAngle={0.02}
								>
									{(pie) =>
										pie.arcs.map((arc, index) => {
											const [centroidX, centroidY] = pie.path.centroid(arc);
											const hasSpaceForLabel = arc.endAngle - arc.startAngle > 0.3;
											const arcPath = pie.path(arc) || "";
											const arcFill = colorScale(arc.data.name);

											return (
												<g
													key={`arc-${arc.data.name}`}
													onMouseMove={(event) => {
														const coords = localPoint(event);
														showTooltip({
															tooltipData: {
																name: arc.data.name,
																count: arc.data.count,
																percentage: arc.data.percentage,
															},
															tooltipLeft: coords?.x,
															tooltipTop: coords?.y,
														});
													}}
													onMouseLeave={hideTooltip}
													style={{ cursor: "pointer" }}
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
					className="!bg-white dark:!bg-gray-800 !shadow-lg !rounded-lg !px-3 !py-2 !border !border-gray-200 dark:!border-gray-700"
				>
					<div className="text-sm">
						<p className="font-semibold text-gray-800 dark:text-gray-200">
							{tooltipData.name}
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
