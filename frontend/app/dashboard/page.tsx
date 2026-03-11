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
	Modal,
	ModalBody,
	ModalContent,
	ModalFooter,
	ModalHeader,
	Spinner,
} from "@heroui/react";
import { formatDistanceToNow } from "date-fns";
import { motion } from "framer-motion";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { mutate } from "swr";
import { videosApi } from "@/api/api";
import CategorizationProgressSSE from "@/components/CategorizationProgressSSE";
import ContinueWatching from "@/components/ContinueWatching";
import Navbar from "@/components/Navbar";
import { useAuthGuard, useVideoStats } from "@/hooks";
import { swrKeys } from "@/lib/swrKeys";

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

export default function Dashboard() {
	const router = useRouter();
	const { isReady, isAuthenticated, user } = useAuthGuard();
	const { stats, isLoading: loading } = useVideoStats();
	const [syncing, setSyncing] = useState(false);
	const [batchSyncing, setBatchSyncing] = useState(false);
	const [batchCategorizing, setBatchCategorizing] = useState(false);
	const [categorizationJobId, setCategorizationJobId] = useState<string | null>(
		null,
	);
	const [batchSyncResult, setBatchSyncResult] = useState<{
		message?: string;
		total_videos_synced?: number;
		videos_categorized?: number;
		pages_fetched?: number;
		[key: string]: unknown;
	} | null>(null);

	const refreshStats = () => {
		mutate(swrKeys.videoStats());
		mutate(swrKeys.categories());
		mutate(swrKeys.tags());
	};

	const handleSync = async () => {
		setSyncing(true);
		try {
			await videosApi.syncVideos({ max_results: 20 });
			refreshStats();
		} catch {
			alert("Failed to sync videos. Please try again.");
		} finally {
			setSyncing(false);
		}
	};

	const handleBatchSync = async () => {
		setBatchSyncing(true);
		setBatchSyncResult(null);
		try {
			const response = await videosApi.syncBatch({ auto_categorize: false });
			setBatchSyncResult(response.data);
			refreshStats();
		} catch {
			alert("Failed to batch sync videos. Please try again.");
		} finally {
			setBatchSyncing(false);
		}
	};

	const handleBatchCategorize = async (maxConcurrent = 10) => {
		setBatchCategorizing(true);
		try {
			// Start SSE job
			const response = await videosApi.startBatchCategorization({
				max_concurrent: maxConcurrent,
			});
			setCategorizationJobId(response.data.job_id);
		} catch {
			alert("Failed to start batch categorization. Please try again.");
			setBatchCategorizing(false);
		}
	};

	const handleCategoryClick = async (category: string) => {
		try {
			router.push(`/videos?category=${encodeURIComponent(category)}`);
		} catch {
			alert("Failed to open category. Please try again.");
		}
	};

	const getGreeting = () => {
		const hour = new Date().getHours();
		if (hour < 12) return "Good morning";
		if (hour < 17) return "Good afternoon";
		return "Good evening";
	};

	const firstName = user?.name?.split(" ")[0] ?? "there";

	// Don't render anything until hydrated and authenticated
	if (!isReady || !isAuthenticated) {
		return (
			<div className="min-h-screen bg-background flex justify-center items-center">
				<Spinner size="lg" color="primary" />
			</div>
		);
	}

	return (
		<div className="min-h-screen bg-background">
			<Navbar />
			<div className="container mx-auto px-4 sm:px-6 py-6 sm:py-8 max-w-7xl">
				<div className="space-y-4 sm:space-y-6">
					{/* Editorial Header */}
					<div className="flex flex-col sm:flex-row justify-between items-start sm:items-end gap-4">
						<div>
							<h1 className="font-display text-2xl sm:text-3xl font-bold text-text-primary tracking-tight">
								{getGreeting()},{" "}
								<span className="text-[#E63946]">{firstName}.</span>
							</h1>
							{user?.last_sync_at && (
								<p className="text-xs text-text-secondary mt-1">
									Last synced{" "}
									{formatDistanceToNow(new Date(user.last_sync_at), {
										addSuffix: true,
									})}
								</p>
							)}
						</div>
						<div className="flex flex-col sm:flex-row gap-2 sm:gap-3 w-full sm:w-auto">
							<Button
								color="secondary"
								size="md"
								variant="flat"
								className="w-full sm:w-auto"
								onPress={handleBatchSync}
								isLoading={batchSyncing}
							>
								<span className="hidden sm:inline">Sync All Videos</span>
								<span className="sm:hidden">Sync All</span>
							</Button>
							<Button
								color="primary"
								size="md"
								className="w-full sm:w-auto"
								onPress={handleSync}
								isLoading={syncing}
							>
								Sync Latest (20)
							</Button>
						</div>
					</div>

					{/* Continue Watching */}
					<ContinueWatching />

					{/* Progress Tracking */}
					{categorizationJobId && (
						<CategorizationProgressSSE
							jobId={categorizationJobId}
							onComplete={() => {
								setBatchCategorizing(false);
								setCategorizationJobId(null);
								refreshStats();
							}}
							onError={() => {
								setBatchCategorizing(false);
								setCategorizationJobId(null);
								alert("Categorization failed. Please try again.");
							}}
						/>
					)}

					{/* Sync Modal */}
					<Modal
						isOpen={syncing}
						isDismissable={false}
						isKeyboardDismissDisabled={true}
						hideCloseButton={true}
						size="md"
						backdrop="blur"
					>
						<ModalContent>
							<ModalHeader className="flex flex-col gap-1">
								Syncing Videos
							</ModalHeader>
							<ModalBody className="py-8">
								<div className="flex flex-col items-center gap-4">
									<Spinner size="lg" color="primary" />
									<div className="text-center space-y-2">
										<p className="text-lg font-semibold">Please wait...</p>
										<p className="text-sm text-text-secondary">
											Fetching your liked videos from YouTube and categorizing
											them with AI.
										</p>
										<p className="text-sm text-text-secondary">
											This may take a few minutes depending on the number of
											videos.
										</p>
									</div>
								</div>
							</ModalBody>
						</ModalContent>
					</Modal>

					{/* Batch Sync Modal */}
					<Modal
						isOpen={batchSyncing || batchSyncResult !== null}
						onClose={() => setBatchSyncResult(null)}
						isDismissable={!batchSyncing}
						isKeyboardDismissDisabled={batchSyncing}
						hideCloseButton={batchSyncing}
						size="lg"
						backdrop="blur"
					>
						<ModalContent>
							<ModalHeader className="flex flex-col gap-1">
								{batchSyncing ? "Syncing All Videos" : "Sync Complete"}
							</ModalHeader>
							<ModalBody className="py-8">
								{batchSyncing ? (
									<div className="flex flex-col items-center gap-4">
										<Spinner size="lg" color="secondary" />
										<div className="text-center space-y-2">
											<p className="text-lg font-semibold">
												Syncing all your liked videos...
											</p>
											<p className="text-sm text-text-secondary">
												This will fetch all your liked videos from YouTube
												without limit.
											</p>
											<p className="text-sm text-text-secondary">
												For 1000+ videos, this may take 5-10 minutes. Please be
												patient.
											</p>
											<p className="text-xs text-text-secondary mt-4">
												You can check the browser console for progress updates.
											</p>
										</div>
									</div>
								) : batchSyncResult ? (
									<div className="space-y-4">
										<div className="text-center">
											<p className="text-2xl mb-4">✅</p>
											<p className="text-lg font-semibold mb-2">
												{batchSyncResult.message}
											</p>
										</div>
										<div className="bg-surface-elevated rounded-lg p-4 space-y-2">
											<div className="flex justify-between">
												<span className="text-text-secondary">
													Total Videos Synced:
												</span>
												<span className="font-semibold font-mono-editorial">
													{batchSyncResult.total_videos_synced}
												</span>
											</div>
											<div className="flex justify-between">
												<span className="text-text-secondary">
													Pages Fetched:
												</span>
												<span className="font-semibold font-mono-editorial">
													{batchSyncResult.pages_fetched}
												</span>
											</div>
											{(batchSyncResult.videos_categorized ?? 0) > 0 && (
												<div className="flex justify-between">
													<span className="text-text-secondary">
														Videos Categorized:
													</span>
													<span className="font-semibold font-mono-editorial">
														{batchSyncResult.videos_categorized}
													</span>
												</div>
											)}
										</div>
									</div>
								) : null}
							</ModalBody>
							{batchSyncResult && (
								<ModalFooter>
									<Button
										color="primary"
										onPress={() => setBatchSyncResult(null)}
									>
										Close
									</Button>
								</ModalFooter>
							)}
						</ModalContent>
					</Modal>

					{loading ? (
						<div className="flex justify-center items-center h-64">
							<Spinner size="lg" color="primary" />
						</div>
					) : stats ? (
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
											<p className="text-xs text-text-secondary mt-2">
												AI-tagged
											</p>
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
											<p className="text-xs text-text-secondary mt-2">
												Needs tagging
											</p>
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
											<p className="text-xs text-text-secondary mt-2">
												Organized
											</p>
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
										{stats && stats.uncategorized > 0 && (
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
														onPress={() => handleBatchCategorize(10)}
													>
														Fast (Recommended)
													</DropdownItem>
													<DropdownItem
														key="faster"
														description="20 concurrent requests (May hit rate limits)"
														onPress={() => handleBatchCategorize(20)}
													>
														Faster
													</DropdownItem>
													<DropdownItem
														key="fastest"
														description="30 concurrent requests (Higher rate limit risk)"
														onPress={() => handleBatchCategorize(30)}
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
															onClick={() => handleCategoryClick(category.name)}
															onKeyDown={(e) => {
																if (e.key === "Enter" || e.key === " ") {
																	e.preventDefault();
																	handleCategoryClick(category.name);
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
					) : (
						<Card className="bg-surface border border-border shadow-none">
							<CardBody>
								<p className="text-center text-text-secondary">
									Failed to load stats
								</p>
							</CardBody>
						</Card>
					)}
				</div>
			</div>
		</div>
	);
}
