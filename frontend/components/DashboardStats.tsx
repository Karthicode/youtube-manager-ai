"use client";

import {
	Button,
	Card,
	CardBody,
	CardHeader,
	Chip,
	Divider,
	Dropdown,
	DropdownItem,
	DropdownMenu,
	DropdownTrigger,
} from "@heroui/react";
import { motion } from "framer-motion";
import Link from "next/link";
import useSWR from "swr";
import { swrKeys } from "@/lib/swrKeys";
import type { VideoStats } from "@/types";

const containerVariants = {
	hidden: {},
	show: {
		transition: {
			staggerChildren: 0.08,
		},
	},
};

const itemVariants = {
	hidden: { opacity: 0, y: 16 },
	show: {
		opacity: 1,
		y: 0,
		transition: { duration: 0.4, ease: "easeOut" as const },
	},
};

interface DashboardStatsProps {
	batchCategorizing: boolean;
	onBatchCategorize: (maxConcurrent?: number) => void;
	onCategoryClick: (category: string) => void;
}

export default function DashboardStats({
	batchCategorizing,
	onBatchCategorize,
	onCategoryClick,
}: DashboardStatsProps) {
	// Suspense mode: the component throws during load and is caught by the
	// parent <Suspense> boundary, which renders <DashboardStatsSkeleton />.
	// With `suspense: true`, `data` is guaranteed to be defined at runtime,
	// but SWR's types don't narrow — cast to the non-nullable type.
	const { data } = useSWR<VideoStats>(swrKeys.videoStats(), {
		suspense: true,
	});
	const stats = data as VideoStats;

	return (
		<>
			{/* Stats Overview */}
			<motion.div
				variants={containerVariants}
				initial="hidden"
				animate="show"
				className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4"
			>
				{/* Liked Videos */}
				<motion.div variants={itemVariants}>
					<Card className="bg-surface border border-border shadow-none h-full">
						<CardBody className="p-4 sm:p-5">
							<h3 className="text-[10px] sm:text-xs text-text-secondary uppercase tracking-widest mb-3">
								Liked Videos
							</h3>
							<p className="font-mono-editorial text-3xl sm:text-4xl font-semibold text-text-primary whitespace-nowrap">
								{stats.liked_videos.toLocaleString()}
							</p>
							<p className="text-xs text-text-secondary mt-2">
								Total in library
							</p>
						</CardBody>
					</Card>
				</motion.div>

				{/* Categorized */}
				<motion.div variants={itemVariants}>
					<Card className="bg-surface border border-border shadow-none h-full">
						<CardBody className="p-4 sm:p-5">
							<h3 className="text-[10px] sm:text-xs text-text-secondary uppercase tracking-widest mb-3">
								Categorized
							</h3>
							<p className="font-mono-editorial text-3xl sm:text-4xl font-semibold text-[#10b981] whitespace-nowrap">
								{stats.categorized.toLocaleString()}
							</p>
							<p className="text-xs text-text-secondary mt-2">AI-tagged</p>
						</CardBody>
					</Card>
				</motion.div>

				{/* Uncategorized */}
				<motion.div variants={itemVariants}>
					<Card className="bg-surface border border-border shadow-none h-full">
						<CardBody className="p-4 sm:p-5">
							<h3 className="text-[10px] sm:text-xs text-text-secondary uppercase tracking-widest mb-3">
								Uncategorized
							</h3>
							<p
								className={`font-mono-editorial text-3xl sm:text-4xl font-semibold whitespace-nowrap ${
									stats.uncategorized > 0
										? "text-[#F59E0B]"
										: "text-text-primary"
								}`}
							>
								{stats.uncategorized.toLocaleString()}
							</p>
							<p className="text-xs text-text-secondary mt-2">Needs tagging</p>
						</CardBody>
					</Card>
				</motion.div>

				{/* Progress */}
				<motion.div variants={itemVariants}>
					<Card className="bg-surface border border-border shadow-none h-full">
						<CardBody className="p-4 sm:p-5">
							<h3 className="text-[10px] sm:text-xs text-text-secondary uppercase tracking-widest mb-3">
								Progress
							</h3>
							<div className="flex items-baseline gap-1">
								<span className="font-mono-editorial text-3xl sm:text-4xl font-semibold text-text-primary">
									{stats.categorization_percentage.toFixed(1)}
								</span>
								<span className="font-mono-editorial text-lg sm:text-xl font-semibold text-text-secondary">
									%
								</span>
							</div>
							<div className="mt-3 h-1.5 bg-border rounded-full overflow-hidden">
								<div
									className="h-full bg-[#E63946] rounded-full transition-all duration-700"
									style={{
										width: `${stats.categorization_percentage}%`,
									}}
								/>
							</div>
							<p className="text-xs text-text-secondary mt-2">Organized</p>
						</CardBody>
					</Card>
				</motion.div>
			</motion.div>

			{/* Quick Actions */}
			<Card className="bg-surface border border-border shadow-none">
				<CardHeader className="pb-2 sm:pb-3">
					<h3 className="text-base sm:text-lg font-semibold font-display text-text-primary">
						Quick Actions
					</h3>
				</CardHeader>
				<Divider className="bg-[#1E1E2A]" />
				<CardBody className="pt-3 sm:pt-4">
					<div className="flex flex-wrap justify-center gap-2 sm:gap-3">
						<Button
							color="primary"
							variant="flat"
							as={Link}
							href="/videos"
							radius="md"
							size="md"
							className="min-w-[140px] flex-1 sm:flex-none"
						>
							View All Videos
						</Button>
						<Button
							color="secondary"
							variant="flat"
							as={Link}
							href="/playlists"
							radius="md"
							size="md"
							className="min-w-[140px] flex-1 sm:flex-none"
						>
							View Playlists
						</Button>
						<Button
							color="success"
							variant="flat"
							as={Link}
							href="/videos?categorized=false"
							radius="md"
							size="md"
							className="min-w-[140px] flex-1 sm:flex-none"
						>
							View Uncategorized
						</Button>
						{stats.uncategorized > 0 && (
							<Dropdown>
								<DropdownTrigger>
									<Button
										color="warning"
										variant="solid"
										isLoading={batchCategorizing}
										radius="md"
										size="md"
										className="min-w-[140px] flex-1 sm:flex-none"
									>
										Categorize All ({stats.uncategorized})
									</Button>
								</DropdownTrigger>
								<DropdownMenu aria-label="Categorization options">
									<DropdownItem
										key="fast"
										description="10 concurrent requests with real-time progress"
										onPress={() => onBatchCategorize(10)}
									>
										Fast (Recommended)
									</DropdownItem>
									<DropdownItem
										key="faster"
										description="20 concurrent requests (May hit rate limits)"
										onPress={() => onBatchCategorize(20)}
									>
										Faster
									</DropdownItem>
									<DropdownItem
										key="fastest"
										description="30 concurrent requests (Higher rate limit risk)"
										onPress={() => onBatchCategorize(30)}
									>
										Fastest
									</DropdownItem>
								</DropdownMenu>
							</Dropdown>
						)}
					</div>
				</CardBody>
			</Card>

			{/* Top Categories + Top Tags */}
			<div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
				{/* Top Categories — visual bar chart */}
				<Card className="bg-surface border border-border shadow-none">
					<CardHeader className="pb-2 sm:pb-3 flex justify-between items-center">
						<h3 className="text-base sm:text-lg font-semibold font-display text-text-primary">
							Top Categories
						</h3>
						<Button
							color="primary"
							variant="flat"
							size="sm"
							as={Link}
							href="/videos"
						>
							View All
						</Button>
					</CardHeader>
					<Divider className="bg-[#1E1E2A]" />
					<CardBody className="pt-3 sm:pt-4">
						{stats.top_categories.length > 0 ? (
							<div className="space-y-2">
								{(() => {
									const maxCount = Math.max(
										...stats.top_categories.map((c) => c.count),
									);
									return stats.top_categories.map((category) => (
										/* biome-ignore lint/a11y/useSemanticElements: Using div with role="button" for layout flexibility */
										<div
											key={category.name}
											role="button"
											tabIndex={0}
											onClick={() => onCategoryClick(category.name)}
											onKeyDown={(e) => {
												if (e.key === "Enter" || e.key === " ") {
													e.preventDefault();
													onCategoryClick(category.name);
												}
											}}
											className="group cursor-pointer"
										>
											<div className="flex justify-between items-center mb-1">
												<span className="font-medium text-text-primary text-sm group-hover:text-[#E63946] transition-colors">
													{category.name}
												</span>
												<Chip
													color="primary"
													variant="flat"
													size="sm"
													radius="md"
												>
													{category.count}
												</Chip>
											</div>
											<div className="h-1 bg-border rounded-full overflow-hidden">
												<div
													className="h-full bg-[#E63946] rounded-full transition-all duration-500 group-hover:bg-[#E63946]/80"
													style={{
														width: `${(category.count / maxCount) * 100}%`,
													}}
												/>
											</div>
										</div>
									));
								})()}
							</div>
						) : (
							<p className="text-text-secondary text-center py-4">
								No categories yet
							</p>
						)}
					</CardBody>
				</Card>

				{/* Top Tags */}
				<Card className="bg-surface border border-border shadow-none">
					<CardHeader className="pb-2 sm:pb-3">
						<h3 className="text-base sm:text-lg font-semibold font-display text-text-primary">
							Top Tags
						</h3>
					</CardHeader>
					<Divider className="bg-[#1E1E2A]" />
					<CardBody className="pt-3 sm:pt-4">
						{stats.top_tags.length > 0 ? (
							<div className="flex flex-wrap gap-2">
								{stats.top_tags.map((tag) => (
									<Chip
										key={tag.name}
										variant="flat"
										size="sm"
										radius="md"
										className="bg-surface-elevated text-text-secondary"
									>
										{tag.name} · {tag.count}
									</Chip>
								))}
							</div>
						) : (
							<p className="text-text-secondary text-center py-4">
								No tags yet
							</p>
						)}
					</CardBody>
				</Card>
			</div>
		</>
	);
}
