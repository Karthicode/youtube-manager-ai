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
import { useCallback, useEffect, useState } from "react";
import { videosApi } from "@/api/api";
import CategorizationProgressSSE from "@/components/CategorizationProgressSSE";
import Navbar from "@/components/Navbar";
import { useAuthGuard } from "@/hooks";
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

export default function Dashboard() {
	const router = useRouter();
	const { isReady, isAuthenticated, user } = useAuthGuard();
	const [stats, setStats] = useState<VideoStats | null>(null);
	const [loading, setLoading] = useState(true);
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

	const fetchStats = useCallback(async () => {
		try {
			const response = await videosApi.getVideoStats();
			setStats(response.data);
		} catch {
			// Stats fetch failed silently - UI will show loading/empty state
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		if (!isReady || !isAuthenticated) return;
		fetchStats();
	}, [isReady, isAuthenticated, fetchStats]);

	const handleSync = async () => {
		setSyncing(true);
		try {
			await videosApi.syncVideos({ max_results: 20 });
			await fetchStats();
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
			await fetchStats();
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
			<div className="min-h-screen bg-[#08080C] flex justify-center items-center">
				<Spinner size="lg" color="primary" />
			</div>
		);
	}

	return (
		<div className="min-h-screen bg-[#08080C]">
			<Navbar />
			<div className="container mx-auto px-4 sm:px-6 py-6 sm:py-8 max-w-7xl">
				<div className="space-y-4 sm:space-y-6">
					{/* Editorial Header */}
					<div className="flex flex-col sm:flex-row justify-between items-start sm:items-end gap-4">
						<div>
							<h1 className="font-display text-2xl sm:text-3xl font-bold text-[#F2F2F7] tracking-tight">
								{getGreeting()},{" "}
								<span className="text-[#E63946]">{firstName}.</span>
							</h1>
							{user?.last_sync_at && (
								<p className="text-xs text-[#6B6B7E] mt-1">
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

					{/* Progress Tracking */}
					{categorizationJobId && (
						<CategorizationProgressSSE
							jobId={categorizationJobId}
							onComplete={() => {
								setBatchCategorizing(false);
								setCategorizationJobId(null);
								fetchStats();
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
										<p className="text-sm text-[#6B6B7E]">
											Fetching your liked videos from YouTube and categorizing
											them with AI.
										</p>
										<p className="text-sm text-[#6B6B7E]">
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
											<p className="text-sm text-[#6B6B7E]">
												This will fetch all your liked videos from YouTube
												without limit.
											</p>
											<p className="text-sm text-[#6B6B7E]">
												For 1000+ videos, this may take 5-10 minutes. Please be
												patient.
											</p>
											<p className="text-xs text-[#6B6B7E] mt-4">
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
										<div className="bg-[#16161E] rounded-lg p-4 space-y-2">
											<div className="flex justify-between">
												<span className="text-[#6B6B7E]">
													Total Videos Synced:
												</span>
												<span className="font-semibold font-mono-editorial">
													{batchSyncResult.total_videos_synced}
												</span>
											</div>
											<div className="flex justify-between">
												<span className="text-[#6B6B7E]">Pages Fetched:</span>
												<span className="font-semibold font-mono-editorial">
													{batchSyncResult.pages_fetched}
												</span>
											</div>
											{(batchSyncResult.videos_categorized ?? 0) > 0 && (
												<div className="flex justify-between">
													<span className="text-[#6B6B7E]">
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
								className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-6"
							>
								{[
									{ label: "Liked Videos", value: stats.liked_videos },
									{ label: "Categorized", value: stats.categorized },
									{ label: "Uncategorized", value: stats.uncategorized },
								].map((stat) => (
									<motion.div key={stat.label} variants={itemVariants}>
										<Card className="bg-[#0F0F14] border border-[#1E1E2A] shadow-none">
											<CardBody className="p-4 sm:p-6">
												<h3 className="text-xs text-[#6B6B7E] uppercase tracking-widest mb-3">
													{stat.label}
												</h3>
												<p className="stat-number text-[#F2F2F7]">
													{stat.value}
												</p>
											</CardBody>
										</Card>
									</motion.div>
								))}
							</motion.div>

							{/* Quick Actions */}
							<Card className="bg-[#0F0F14] border border-[#1E1E2A] shadow-none">
								<CardHeader className="pb-2 sm:pb-3">
									<h3 className="text-base sm:text-lg font-semibold font-display text-[#F2F2F7]">
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

							{/* Top Categories + Getting Started */}
							<div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
								<Card className="bg-[#0F0F14] border border-[#1E1E2A] shadow-none">
									<CardHeader className="pb-2 sm:pb-3">
										<h3 className="text-base sm:text-lg font-semibold font-display text-[#F2F2F7]">
											Top Categories
										</h3>
									</CardHeader>
									<Divider className="bg-[#1E1E2A]" />
									<CardBody className="pt-3 sm:pt-4">
										{stats.top_categories.length > 0 ? (
											<div className="space-y-1">
												{stats.top_categories.map((category) => (
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
														className="flex justify-between items-center p-2 rounded-lg hover:bg-[#16161E] transition-colors cursor-pointer"
													>
														<span className="font-medium text-[#F2F2F7] text-sm">
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
												))}
											</div>
										) : (
											<p className="text-[#6B6B7E] text-center py-4">
												No categories yet
											</p>
										)}
									</CardBody>
								</Card>

								<Card className="bg-[#0F0F14] border border-[#1E1E2A] shadow-none">
									<CardHeader className="pb-2 sm:pb-3">
										<h3 className="text-base sm:text-lg font-semibold font-display text-[#F2F2F7]">
											Getting Started
										</h3>
									</CardHeader>
									<Divider className="bg-[#1E1E2A]" />
									<CardBody className="pt-3 sm:pt-4">
										<ul aria-label="Getting started tips" className="space-y-3">
											{stats.total_videos === 0 && (
												<li className="flex items-start gap-3 p-3 rounded-lg border border-[#3B82F6]/20 bg-[#3B82F6]/5">
													<span
														className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-[#3B82F6] text-white text-sm font-medium"
														aria-hidden="true"
													>
														1
													</span>
													<div>
														<p className="font-medium text-[#F2F2F7]">
															Sync your videos
														</p>
														<p className="text-sm text-[#6B6B7E]">
															Click &quot;Sync Latest&quot; or &quot;Sync All
															Videos&quot; to import your liked videos from
															YouTube.
														</p>
													</div>
												</li>
											)}
											{stats.total_videos > 0 && stats.uncategorized > 0 && (
												<li className="flex items-start gap-3 p-3 rounded-lg border border-[#F59E0B]/20 bg-[#F59E0B]/5">
													<span
														className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-[#F59E0B] text-white text-sm font-medium"
														aria-hidden="true"
													>
														!
													</span>
													<div>
														<p className="font-medium text-[#F2F2F7]">
															Categorize your videos
														</p>
														<p className="text-sm text-[#6B6B7E]">
															You have {stats.uncategorized} uncategorized video
															{stats.uncategorized !== 1 ? "s" : ""}. Use
															&quot;Categorize All&quot; in Quick Actions to
															organize them with AI.
														</p>
													</div>
												</li>
											)}
											{stats.categorization_percentage === 100 &&
												stats.total_videos > 0 && (
													<li className="flex items-start gap-3 p-3 rounded-lg border border-[#10B981]/20 bg-[#10B981]/5">
														<span
															className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-[#10B981] text-white text-sm font-medium"
															aria-hidden="true"
														>
															✓
														</span>
														<div>
															<p className="font-medium text-[#F2F2F7]">
																All caught up!
															</p>
															<p className="text-sm text-[#6B6B7E]">
																All your videos are categorized. Browse them by
																category or create playlists.
															</p>
														</div>
													</li>
												)}
											<li className="flex items-start gap-3 p-3 rounded-lg border border-[#1E1E2A] bg-[#16161E]/50">
												<span
													className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-[#2A2A38] text-[#F2F2F7] text-sm font-medium"
													aria-hidden="true"
												>
													?
												</span>
												<div>
													<p className="font-medium text-[#F2F2F7]">
														Keyboard navigation
													</p>
													<p className="text-sm text-[#6B6B7E]">
														Use{" "}
														<kbd className="px-1.5 py-0.5 text-xs font-mono-editorial bg-[#1E1E2A] rounded">
															Tab
														</kbd>{" "}
														to navigate between elements and{" "}
														<kbd className="px-1.5 py-0.5 text-xs font-mono-editorial bg-[#1E1E2A] rounded">
															Enter
														</kbd>{" "}
														to activate buttons.
													</p>
												</div>
											</li>
										</ul>
									</CardBody>
								</Card>
							</div>
						</>
					) : (
						<Card className="bg-[#0F0F14] border border-[#1E1E2A] shadow-none">
							<CardBody>
								<p className="text-center text-[#6B6B7E]">
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
