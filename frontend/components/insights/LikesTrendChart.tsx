"use client";

import { AxisBottom, AxisLeft } from "@visx/axis";
import { localPoint } from "@visx/event";
import { LinearGradient } from "@visx/gradient";
import { GridRows } from "@visx/grid";
import { Group } from "@visx/group";
import { scaleLinear, scalePoint } from "@visx/scale";
import { AreaClosed, LinePath } from "@visx/shape";
import { TooltipWithBounds, useTooltip } from "@visx/tooltip";
import type { TemporalData } from "@/types";
import ChartWrapper from "./ChartWrapper";

interface LikesTrendChartProps {
	data: TemporalData[];
	loading?: boolean;
	error?: string;
}

export default function LikesTrendChart({
	data,
	loading = false,
	error,
}: LikesTrendChartProps) {
	const {
		tooltipOpen,
		tooltipData,
		tooltipLeft,
		tooltipTop,
		showTooltip,
		hideTooltip,
	} = useTooltip<TemporalData>();

	const margin = { top: 20, right: 20, bottom: 40, left: 50 };

	// Format month label for display
	const formatMonthLabel = (label: string) => {
		const [year, month] = label.split("-");
		const date = new Date(parseInt(year, 10), parseInt(month, 10) - 1);
		return date.toLocaleDateString("en-US", {
			month: "short",
			year: "2-digit",
		});
	};

	return (
		<>
			<ChartWrapper
				title="Likes Over Time"
				subtitle="Monthly trend of liked videos"
				loading={loading}
				error={error}
				height="h-[250px]"
			>
				{({ width, height }) => {
					const xMax = Math.max(0, width - margin.left - margin.right);
					const yMax = Math.max(0, height - margin.top - margin.bottom);

					// Don't render if dimensions are too small
					if (xMax < 10 || yMax < 10) {
						return <svg width={width} height={height} />;
					}

					const xScale = scalePoint<string>({
						domain: data.map((d) => d.label),
						range: [0, xMax],
						padding: 0.5,
					});

					const yScale = scaleLinear<number>({
						domain: [0, Math.max(...data.map((d) => d.count), 1) * 1.1],
						range: [yMax, 0],
						nice: true,
					});

					// Show fewer tick labels on smaller screens
					const tickInterval = Math.ceil(data.length / (width < 500 ? 4 : 8));
					const tickValues = data
						.filter((_, i) => i % tickInterval === 0)
						.map((d) => d.label);

					return (
						<svg
							width={width}
							height={height}
							role="img"
							aria-label="Likes trend over time chart"
						>
							<title>Monthly Likes Trend</title>
							<LinearGradient
								id="area-gradient"
								from="#3B82F6"
								to="#3B82F6"
								fromOpacity={0.4}
								toOpacity={0.05}
							/>
							<Group left={margin.left} top={margin.top}>
								<GridRows
									scale={yScale}
									width={xMax}
									strokeDasharray="3,3"
									stroke="currentColor"
									strokeOpacity={0.1}
									className="text-gray-400"
								/>
								<AreaClosed
									data={data}
									x={(d) => xScale(d.label) || 0}
									y={(d) => yScale(d.count)}
									yScale={yScale}
									fill="url(#area-gradient)"
								/>
								<LinePath
									data={data}
									x={(d) => xScale(d.label) || 0}
									y={(d) => yScale(d.count)}
									stroke="#3B82F6"
									strokeWidth={2}
								/>
								{/* biome-ignore lint/a11y/noStaticElementInteractions: Hover area for tooltip display */}
								<rect
									x={0}
									y={0}
									width={xMax}
									height={yMax}
									fill="transparent"
									onMouseMove={(event) => {
										const coords = localPoint(event);
										if (!coords) return;
										const x = coords.x;
										const domain = data.map((d) => d.label);
										const index = Math.round((x / xMax) * (domain.length - 1));
										const d =
											data[Math.max(0, Math.min(index, data.length - 1))];
										if (d) {
											showTooltip({
												tooltipData: d,
												tooltipLeft: (xScale(d.label) || 0) + margin.left,
												tooltipTop: yScale(d.count) + margin.top,
											});
										}
									}}
									onMouseLeave={hideTooltip}
								/>
								{/* Data points */}
								{data.map((d) => (
									<circle
										key={`point-${d.label}`}
										cx={xScale(d.label) || 0}
										cy={yScale(d.count)}
										r={3}
										fill="#3B82F6"
										className="pointer-events-none"
									/>
								))}
								<AxisBottom
									top={yMax}
									scale={xScale}
									tickValues={tickValues}
									tickFormat={formatMonthLabel}
									stroke="currentColor"
									tickStroke="transparent"
									tickLabelProps={() => ({
										fill: "currentColor",
										fontSize: 10,
										textAnchor: "middle" as const,
										className: "text-gray-500 dark:text-gray-400",
									})}
								/>
								<AxisLeft
									scale={yScale}
									stroke="transparent"
									tickStroke="transparent"
									numTicks={5}
									tickLabelProps={() => ({
										fill: "currentColor",
										fontSize: 10,
										textAnchor: "end" as const,
										dx: -4,
										dy: 4,
										className: "text-gray-500 dark:text-gray-400",
									})}
								/>
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
							{formatMonthLabel(tooltipData.label)}
						</p>
						<p className="text-gray-600 dark:text-gray-400">
							{tooltipData.count} videos liked
						</p>
					</div>
				</TooltipWithBounds>
			)}
		</>
	);
}
