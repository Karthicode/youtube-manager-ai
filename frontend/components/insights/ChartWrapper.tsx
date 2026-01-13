"use client";

import { Card, CardBody, CardHeader, Spinner } from "@heroui/react";
import { ParentSize } from "@visx/responsive";
import type { ReactNode } from "react";

interface ChartWrapperProps {
	title: string;
	subtitle?: string;
	loading?: boolean;
	error?: string;
	height?: string;
	children: (props: { width: number; height: number }) => ReactNode;
}

export default function ChartWrapper({
	title,
	subtitle,
	loading = false,
	error,
	height = "h-[300px]",
	children,
}: ChartWrapperProps) {
	return (
		<Card className="shadow-lg">
			<CardHeader className="pb-2">
				<div>
					<h3 className="text-base sm:text-lg font-semibold">{title}</h3>
					{subtitle && (
						<p className="text-xs sm:text-sm text-gray-500 dark:text-gray-400">
							{subtitle}
						</p>
					)}
				</div>
			</CardHeader>
			<CardBody className="pt-2">
				<div className={`${height} w-full`}>
					{loading ? (
						<div className="h-full w-full flex items-center justify-center">
							<Spinner size="lg" />
						</div>
					) : error ? (
						<div className="h-full w-full flex items-center justify-center">
							<p className="text-red-500 text-sm">{error}</p>
						</div>
					) : (
						<ParentSize>
							{({ width, height }) => children({ width, height })}
						</ParentSize>
					)}
				</div>
			</CardBody>
		</Card>
	);
}
