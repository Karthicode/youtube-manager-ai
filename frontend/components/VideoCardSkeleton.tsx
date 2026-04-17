"use client";

import { Card, CardBody, CardFooter, Skeleton } from "@heroui/react";

interface VideoCardSkeletonProps {
	viewMode?: "grid" | "list";
}

export default function VideoCardSkeleton({
	viewMode = "grid",
}: VideoCardSkeletonProps) {
	if (viewMode === "list") {
		return (
			<Card className="w-full border border-border bg-surface shadow-none">
				<CardBody className="p-3 sm:p-4">
					<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-4">
						<div className="flex-1 min-w-0 space-y-2">
							<Skeleton className="h-4 w-3/4 rounded" />
							<div className="flex items-center gap-3">
								<Skeleton className="h-3 w-24 rounded" />
								<Skeleton className="h-3 w-16 rounded" />
								<Skeleton className="h-3 w-20 rounded" />
							</div>
						</div>
						<div className="flex items-center gap-2 shrink-0">
							<Skeleton className="h-6 w-20 rounded-md" />
							<Skeleton className="h-6 w-16 rounded-md" />
						</div>
					</div>
				</CardBody>
			</Card>
		);
	}

	// Grid mode (default)
	return (
		<Card className="w-full bg-surface border border-border shadow-none overflow-hidden">
			<CardBody className="p-0">
				{/* Thumbnail: matches h-[160px] sm:h-[200px] in VideoCard */}
				<Skeleton className="h-[160px] sm:h-[200px] w-full rounded-none" />
				<div className="p-2 sm:p-3 space-y-1 sm:space-y-2">
					{/* Title – 2 lines */}
					<Skeleton className="h-3 w-full rounded" />
					<Skeleton className="h-3 w-4/5 rounded" />
					{/* Channel */}
					<Skeleton className="h-3 w-1/2 rounded" />
					{/* Stats row */}
					<div className="flex items-center gap-2">
						<Skeleton className="h-3 w-16 rounded" />
						<Skeleton className="h-3 w-20 rounded" />
					</div>
				</div>
			</CardBody>
			{/* Footer chips */}
			<CardFooter className="flex-col items-start gap-2 pt-0 px-2 sm:px-3 pb-2 sm:pb-3">
				<div className="flex flex-wrap gap-1 w-full">
					<Skeleton className="h-6 w-20 rounded-md" />
					<Skeleton className="h-6 w-16 rounded-md" />
					<Skeleton className="h-6 w-14 rounded-md" />
				</div>
			</CardFooter>
		</Card>
	);
}
