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
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { videosApi } from "@/api/api";
import CategorizationProgressSSE from "@/components/CategorizationProgressSSE";
import Navbar from "@/components/Navbar";
import { useAuthGuard } from "@/hooks";
import type { VideoStats } from "@/types";

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
		} catch (error) {
			console.error("Failed to fetch stats:", error);
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
		} catch (error) {
			console.error("Failed to sync videos:", error);
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
		} catch (error) {
			console.error("Failed to batch sync videos:", error);
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
		} catch (error) {
			console.error("Failed to start batch categorization:", error);
			alert("Failed to start batch categorization. Please try again.");
			setBatchCategorizing(false);
		}
	};

	const handleCategoryClick = async (category: string) => {
		try {
			// Navigate to videos page and include the category name in query params
			router.push(`/videos?category=${encodeURIComponent(category)}`);
		} catch (error) {
			console.error("Failed to navigate to category:", error);
			alert("Failed to open category. Please try again.");
		}
	};

	// Don't render anything until hydrated and authenticated
	if (!isReady || !isAuthenticated) {
		return (
			<div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex justify-center items-center">
				<Spinner size="lg" />
			</div>
		);
	}

	return (
		<div className="min-h-screen bg-gray-50 dark:bg-gray-900">
			<Navbar />
			<div className="container mx-auto px-4 sm:px-6 py-6 sm:py-8 max-w-7xl">
				<div className="space-y-4 sm:space-y-6">
					{/* Header */}
					<div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
						<div>
							<h1 className="text-2xl sm:text-3xl font-bold">Dashboard</h1>
							<p className="text-sm sm:text-base text-gray-600 dark:text-gray-400 mt-1">
								Welcome back, {user?.name}!
							</p>
							{user?.last_sync_at && (
								<p className="text-xs sm:text-sm text-gray-500 dark:text-gray-500 mt-1">
									Last synced:{" "}
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
							onError={(error) => {
								console.error("Categorization error:", error);
								setBatchCategorizing(false);
								setCategorizationJobId(null);
								alert(`Categorization failed: ${error}`);
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
										<p className="text-sm text-gray-600 dark:text-gray-400">
											Fetching your liked videos from YouTube and categorizing
											them with AI.
										</p>
										<p className="text-sm text-gray-600 dark:text-gray-400">
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
											<p className="text-sm text-gray-600 dark:text-gray-400">
												This will fetch all your liked videos from YouTube
												without limit.
											</p>
											<p className="text-sm text-gray-600 dark:text-gray-400">
												For 1000+ videos, this may take 5-10 minutes. Please be
												patient.
											</p>
											<p className="text-xs text-gray-500 dark:text-gray-500 mt-4">
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
										<div className="bg-gray-100 dark:bg-gray-800 rounded-lg p-4 space-y-2">
											<div className="flex justify-between">
												<span className="text-gray-600 dark:text-gray-400">
													Total Videos Synced:
												</span>
												<span className="font-semibold">
													{batchSyncResult.total_videos_synced}
												</span>
											</div>
											<div className="flex justify-between">
												<span className="text-gray-600 dark:text-gray-400">
													Pages Fetched:
												</span>
												<span className="font-semibold">
													{batchSyncResult.pages_fetched}
												</span>
											</div>
											{(batchSyncResult.videos_categorized ?? 0) > 0 && (
												<div className="flex justify-between">
													<span className="text-gray-600 dark:text-gray-400">
														Videos Categorized:
													</span>
													<span className="font-semibold">
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
							<Spinner size="lg" />
						</div>
					) : stats ? (
						<>
							{/* Stats Overview */}
							<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
								<Card className="bg-linear-to-br from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-800/20 border-none shadow-lg">
									<CardBody className="p-4 sm:p-6">
										<h3 className="text-xs sm:text-sm font-medium text-gray-600 dark:text-gray-400 mb-1 sm:mb-2">
											Total Videos
										</h3>
										<p className="text-3xl sm:text-4xl lg:text-5xl font-bold text-blue-600 dark:text-blue-400">
											{stats.total_videos}
										</p>
									</CardBody>
								</Card>

								<Card className="bg-linear-to-br from-green-50 to-green-100 dark:from-green-900/20 dark:to-green-800/20 border-none shadow-lg">
									<CardBody className="p-4 sm:p-6">
										<h3 className="text-xs sm:text-sm font-medium text-gray-600 dark:text-gray-400 mb-1 sm:mb-2">
											Categorized
										</h3>
										<p className="text-3xl sm:text-4xl lg:text-5xl font-bold text-green-600 dark:text-green-400">
											{stats.categorized}
										</p>
									</CardBody>
								</Card>

								<Card className="bg-linear-to-br from-orange-50 to-orange-100 dark:from-orange-900/20 dark:to-orange-800/20 border-none shadow-lg">
									<CardBody className="p-4 sm:p-6">
										<h3 className="text-xs sm:text-sm font-medium text-gray-600 dark:text-gray-400 mb-1 sm:mb-2">
											Uncategorized
										</h3>
										<p className="text-3xl sm:text-4xl lg:text-5xl font-bold text-orange-600 dark:text-orange-400">
											{stats.uncategorized}
										</p>
									</CardBody>
								</Card>
							</div>

							{/* Quick Actions */}
							<Card className="shadow-lg">
								<CardHeader className="pb-2 sm:pb-3">
									<h3 className="text-base sm:text-lg font-semibold">
										Quick Actions
									</h3>
								</CardHeader>
								<Divider />
								<CardBody className="pt-3 sm:pt-4">
									<div className="flex flex-wrap justify-center gap-2 sm:gap-3">
										<Button
											color="primary"
											variant="flat"
											onPress={() => router.push("/videos")}
											radius="md"
											size="md"
											className="min-w-[140px] flex-1 sm:flex-none"
										>
											View All Videos
										</Button>
										<Button
											color="secondary"
											variant="flat"
											onPress={() => router.push("/playlists")}
											radius="md"
											size="md"
											className="min-w-[140px] flex-1 sm:flex-none"
										>
											View Playlists
										</Button>
										<Button
											color="success"
											variant="flat"
											onPress={() => router.push("/videos?categorized=false")}
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

							{/* Top Categories */}
							<div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
								<Card className="shadow-lg">
									<CardHeader className="pb-2 sm:pb-3">
										<h3 className="text-base sm:text-lg font-semibold">
											Top Categories
										</h3>
									</CardHeader>
									<Divider />
									<CardBody className="pt-3 sm:pt-4">
										{stats.top_categories.length > 0 ? (
											<div className="space-y-3">
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
														className="flex justify-between items-center p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors cursor-pointer"
													>
														<span className="font-medium text-gray-700 dark:text-gray-300">
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
											<p className="text-gray-500 text-center py-4">
												No categories yet
											</p>
										)}
									</CardBody>
								</Card>

								<Card className="shadow-lg">
									<CardHeader className="pb-2 sm:pb-3">
										<h3 className="text-base sm:text-lg font-semibold">
											Getting Started
										</h3>
									</CardHeader>
									<Divider />
									<CardBody className="pt-3 sm:pt-4">
										<ul aria-label="Getting started tips" className="space-y-3">
											{stats.total_videos === 0 && (
												<li className="flex items-start gap-3 p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20">
													<span
														className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-blue-500 text-white text-sm font-medium"
														aria-hidden="true"
													>
														1
													</span>
													<div>
														<p className="font-medium text-gray-800 dark:text-gray-200">
															Sync your videos
														</p>
														<p className="text-sm text-gray-600 dark:text-gray-400">
															Click &quot;Sync Latest&quot; or &quot;Sync All
															Videos&quot; to import your liked videos from
															YouTube.
														</p>
													</div>
												</li>
											)}
											{stats.total_videos > 0 && stats.uncategorized > 0 && (
												<li className="flex items-start gap-3 p-3 rounded-lg bg-orange-50 dark:bg-orange-900/20">
													<span
														className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-orange-500 text-white text-sm font-medium"
														aria-hidden="true"
													>
														!
													</span>
													<div>
														<p className="font-medium text-gray-800 dark:text-gray-200">
															Categorize your videos
														</p>
														<p className="text-sm text-gray-600 dark:text-gray-400">
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
													<li className="flex items-start gap-3 p-3 rounded-lg bg-green-50 dark:bg-green-900/20">
														<span
															className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-green-500 text-white text-sm font-medium"
															aria-hidden="true"
														>
															✓
														</span>
														<div>
															<p className="font-medium text-gray-800 dark:text-gray-200">
																All caught up!
															</p>
															<p className="text-sm text-gray-600 dark:text-gray-400">
																All your videos are categorized. Browse them by
																category or create playlists.
															</p>
														</div>
													</li>
												)}
											<li className="flex items-start gap-3 p-3 rounded-lg bg-gray-50 dark:bg-gray-800/50">
												<span
													className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-gray-500 text-white text-sm font-medium"
													aria-hidden="true"
												>
													?
												</span>
												<div>
													<p className="font-medium text-gray-800 dark:text-gray-200">
														Keyboard navigation
													</p>
													<p className="text-sm text-gray-600 dark:text-gray-400">
														Use{" "}
														<kbd className="px-1.5 py-0.5 text-xs font-mono bg-gray-200 dark:bg-gray-700 rounded">
															Tab
														</kbd>{" "}
														to navigate between elements and{" "}
														<kbd className="px-1.5 py-0.5 text-xs font-mono bg-gray-200 dark:bg-gray-700 rounded">
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
						<Card>
							<CardBody>
								<p className="text-center text-gray-500">
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
