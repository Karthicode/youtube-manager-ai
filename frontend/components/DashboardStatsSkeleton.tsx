"use client";

import { Card, CardBody, CardHeader, Divider, Skeleton } from "@heroui/react";

export default function DashboardStatsSkeleton() {
	return (
		<>
			{/* Stats Overview skeleton */}
			<div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
				{Array.from({ length: 4 }).map((_, i) => (
					<Card
						// biome-ignore lint/suspicious/noArrayIndexKey: Static skeleton placeholders
						key={i}
						className="bg-surface border border-border shadow-none h-full"
					>
						<CardBody className="p-4 sm:p-5">
							<Skeleton className="h-3 w-20 rounded" />
							<Skeleton className="h-9 sm:h-10 w-24 rounded mt-3" />
							<Skeleton className="h-3 w-24 rounded mt-2" />
						</CardBody>
					</Card>
				))}
			</div>

			{/* Quick Actions skeleton */}
			<Card className="bg-surface border border-border shadow-none">
				<CardHeader className="pb-2 sm:pb-3">
					<Skeleton className="h-5 w-32 rounded" />
				</CardHeader>
				<Divider className="bg-[#1E1E2A]" />
				<CardBody className="pt-3 sm:pt-4">
					<div className="flex flex-wrap justify-center gap-2 sm:gap-3">
						{Array.from({ length: 4 }).map((_, i) => (
							<Skeleton
								// biome-ignore lint/suspicious/noArrayIndexKey: Static skeleton placeholders
								key={i}
								className="h-10 w-[140px] rounded-md"
							/>
						))}
					</div>
				</CardBody>
			</Card>

			{/* Top Categories + Top Tags skeleton */}
			<div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
				<Card className="bg-surface border border-border shadow-none">
					<CardHeader className="pb-2 sm:pb-3 flex justify-between items-center">
						<Skeleton className="h-5 w-32 rounded" />
						<Skeleton className="h-8 w-16 rounded" />
					</CardHeader>
					<Divider className="bg-[#1E1E2A]" />
					<CardBody className="pt-3 sm:pt-4">
						<div className="space-y-2">
							{Array.from({ length: 5 }).map((_, i) => (
								// biome-ignore lint/suspicious/noArrayIndexKey: Static skeleton placeholders
								<div key={i}>
									<div className="flex justify-between items-center mb-1">
										<Skeleton className="h-4 w-24 rounded" />
										<Skeleton className="h-5 w-10 rounded" />
									</div>
									<Skeleton className="h-1 w-full rounded-full" />
								</div>
							))}
						</div>
					</CardBody>
				</Card>
				<Card className="bg-surface border border-border shadow-none">
					<CardHeader className="pb-2 sm:pb-3">
						<Skeleton className="h-5 w-24 rounded" />
					</CardHeader>
					<Divider className="bg-[#1E1E2A]" />
					<CardBody className="pt-3 sm:pt-4">
						<div className="flex flex-wrap gap-2">
							{Array.from({ length: 8 }).map((_, i) => (
								<Skeleton
									// biome-ignore lint/suspicious/noArrayIndexKey: Static skeleton placeholders
									key={i}
									className="h-6 w-20 rounded-md"
								/>
							))}
						</div>
					</CardBody>
				</Card>
			</div>
		</>
	);
}
