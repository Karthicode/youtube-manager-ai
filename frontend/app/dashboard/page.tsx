"use client";

import {
	Button,
	Card,
	CardBody,
	CardHeader,
	Chip,
	Divider,
	Modal,
	ModalBody,
	ModalContent,
	ModalFooter,
	ModalHeader,
	Progress,
	Spinner,
} from "@heroui/react";
import { formatDistanceToNow } from "date-fns";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { videosApi } from "@/api/api";
import Navbar from "@/components/Navbar";
import { useAuthStore } from "@/store/auth";
import type { VideoStats } from "@/types";

export default function Dashboard() {
	const router = useRouter();
	const { isAuthenticated, user } = useAuthStore();
	const [stats, setStats] = useState<VideoStats | null>(null);
	const [loading, setLoading] = useState(true);
	const [syncing, setSyncing] = useState(false);
	const [batchSyncing, setBatchSyncing] = useState(false);
	const [batchCategorizing, setBatchCategorizing] = useState(false);
	const [batchSyncResult, setBatchSyncResult] = useState<{
		message?: string;
		total_videos_synced?: number;
		videos_categorized?: number;
		pages_fetched?: number;
		[key: string]: unknown;
	} | null>(null);
	const [categorizationResult, setCategorizationResult] = useState<{
		message?: string;
		total_categorized?: number;
		total_failed?: number;
		total_videos?: number;
		success_rate?: number;
		[key: string]: unknown;
	} | null>(null);
	const [mounted, setMounted] = useState(false);

	// Handle hydration
	useEffect(() => {
		setMounted(true);
	}, []);

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
		// Wait for Zustand to hydrate from localStorage
		if (!mounted) return;

		if (!isAuthenticated) {
			router.push("/");
			return;
		}

		fetchStats();
	}, [mounted, isAuthenticated, router, fetchStats]);

	const handleSync = async () => {
		setSyncing(true);
		try {
			await videosApi.syncVideos({ max_results: 50, auto_categorize: true });
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

	const handleBatchCategorize = async () => {
		setBatchCategorizing(true);
		setCategorizationResult(null);
		try {
			const response = await videosApi.categorizeBatch({ batch_size: 10 });
			setCategorizationResult(response.data);
			await fetchStats();
		} catch (error) {
			console.error("Failed to batch categorize:", error);
			alert("Failed to batch categorize videos. Please try again.");
		} finally {
			setBatchCategorizing(false);
		}
	};

	// Don't render anything until hydrated
	if (!mounted) {
		return (
			<div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex justify-center items-center">
				<Spinner size="lg" />
			</div>
		);
	}

	if (!isAuthenticated) {
		return null;
	}

	return (
		<div className="min-h-screen bg-gray-50 dark:bg-gray-900">
			<Navbar />
			<div className="container mx-auto px-4 py-8 max-w-7xl">
				<div className="space-y-6">
					{/* Header */}
					<div className="flex justify-between items-center">
						<div>
							<h1 className="text-3xl font-bold">Dashboard</h1>
							<p className="text-gray-600 dark:text-gray-400 mt-1">
								Welcome back, {user?.name}!
							</p>
							{user?.last_sync_at && (
								<p className="text-sm text-gray-500 dark:text-gray-500 mt-1">
									Last synced:{" "}
									{formatDistanceToNow(new Date(user.last_sync_at), {
										addSuffix: true,
									})}
								</p>
							)}
						</div>
						<div className="flex gap-3">
							<Button
								color="primary"
								size="lg"
								onPress={handleSync}
								isLoading={syncing}
							>
								Sync Videos (50)
							</Button>
							<Button
								color="secondary"
								size="lg"
								onPress={handleBatchSync}
								isLoading={batchSyncing}
							>
								Sync All Videos
							</Button>
						</div>
					</div>

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

					{/* Batch Categorization Modal */}
					<Modal
						isOpen={batchCategorizing || categorizationResult !== null}
						onClose={() => setCategorizationResult(null)}
						isDismissable={!batchCategorizing}
						isKeyboardDismissDisabled={batchCategorizing}
						hideCloseButton={batchCategorizing}
						size="lg"
						backdrop="blur"
					>
						<ModalContent>
							<ModalHeader className="flex flex-col gap-1">
								{batchCategorizing
									? "Categorizing Videos"
									: "Categorization Complete"}
							</ModalHeader>
							<ModalBody className="py-8">
								{batchCategorizing ? (
									<div className="flex flex-col items-center gap-4">
										<Spinner size="lg" color="success" />
										<div className="text-center space-y-2">
											<p className="text-lg font-semibold">
												Categorizing all uncategorized videos...
											</p>
											<p className="text-sm text-gray-600 dark:text-gray-400">
												Processing videos in parallel batches of 10 for maximum
												efficiency.
											</p>
											<p className="text-sm text-gray-600 dark:text-gray-400">
												This may take several minutes for large numbers of
												videos.
											</p>
											<p className="text-xs text-gray-500 dark:text-gray-500 mt-4">
												You can check the browser console for progress updates.
											</p>
										</div>
									</div>
								) : categorizationResult ? (
									<div className="space-y-4">
										<div className="text-center">
											<p className="text-2xl mb-4">
												{(categorizationResult.total_failed ?? 0) === 0 ? "✅" : "⚠️"}
											</p>
											<p className="text-lg font-semibold mb-2">
												{categorizationResult.message}
											</p>
										</div>
										<div className="bg-gray-100 dark:bg-gray-800 rounded-lg p-4 space-y-2">
											<div className="flex justify-between">
												<span className="text-gray-600 dark:text-gray-400">
													Total Videos:
												</span>
												<span className="font-semibold">
													{categorizationResult.total_videos}
												</span>
											</div>
											<div className="flex justify-between">
												<span className="text-green-600 dark:text-green-400">
													Categorized:
												</span>
												<span className="font-semibold text-green-600 dark:text-green-400">
													{categorizationResult.total_categorized}
												</span>
											</div>
											{(categorizationResult.total_failed ?? 0) > 0 && (
												<div className="flex justify-between">
													<span className="text-red-600 dark:text-red-400">
														Failed:
													</span>
													<span className="font-semibold text-red-600 dark:text-red-400">
														{categorizationResult.total_failed}
													</span>
												</div>
											)}
											<div className="flex justify-between pt-2 border-t border-gray-300 dark:border-gray-600">
												<span className="text-gray-600 dark:text-gray-400">
													Success Rate:
												</span>
												<span className="font-semibold">
													{categorizationResult.success_rate}%
												</span>
											</div>
										</div>
									</div>
								) : null}
							</ModalBody>
							{categorizationResult && (
								<ModalFooter>
									<Button
										color="primary"
										onPress={() => setCategorizationResult(null)}
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
							<div className="grid grid-cols-1 md:grid-cols-3 gap-6">
								<Card className="bg-linear-to-br from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-800/20 border-none shadow-lg">
									<CardBody className="p-6">
										<h3 className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">
											Total Videos
										</h3>
										<p className="text-5xl font-bold text-blue-600 dark:text-blue-400">
											{stats.total_videos}
										</p>
									</CardBody>
								</Card>

								<Card className="bg-linear-to-br from-green-50 to-green-100 dark:from-green-900/20 dark:to-green-800/20 border-none shadow-lg">
									<CardBody className="p-6">
										<h3 className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">
											Categorized
										</h3>
										<p className="text-5xl font-bold text-green-600 dark:text-green-400">
											{stats.categorized}
										</p>
									</CardBody>
								</Card>

								<Card className="bg-linear-to-br from-orange-50 to-orange-100 dark:from-orange-900/20 dark:to-orange-800/20 border-none shadow-lg">
									<CardBody className="p-6">
										<h3 className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">
											Uncategorized
										</h3>
										<p className="text-5xl font-bold text-orange-600 dark:text-orange-400">
											{stats.uncategorized}
										</p>
									</CardBody>
								</Card>
							</div>

							{/* Categorization Progress */}
							<Card className="shadow-lg">
								<CardHeader className="pb-3">
									<h3 className="text-lg font-semibold">
										Categorization Progress
									</h3>
								</CardHeader>
								<CardBody className="pt-4">
									<Progress
										value={stats.categorization_percentage}
										color="primary"
										size="lg"
										showValueLabel
										className="mb-3"
										radius="md"
									/>
									<p className="text-sm text-gray-600 dark:text-gray-400">
										{stats.categorized} of {stats.total_videos} videos
										categorized
									</p>
								</CardBody>
							</Card>

							{/* Top Categories */}
							<div className="grid grid-cols-1 md:grid-cols-2 gap-6">
								<Card className="shadow-lg">
									<CardHeader className="pb-3">
										<h3 className="text-lg font-semibold">Top Categories</h3>
									</CardHeader>
									<Divider />
									<CardBody className="pt-4">
										{stats.top_categories.length > 0 ? (
											<div className="space-y-3">
												{stats.top_categories.map((category) => (
													<div
														key={category.name}
														className="flex justify-between items-center p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
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
									<CardHeader className="pb-3">
										<h3 className="text-lg font-semibold">Top Tags</h3>
									</CardHeader>
									<Divider />
									<CardBody className="pt-4">
										{stats.top_tags.length > 0 ? (
											<div className="flex flex-wrap gap-2">
												{stats.top_tags.map((tag) => (
													<Chip
														key={tag.name}
														variant="bordered"
														size="sm"
														radius="md"
													>
														{tag.name} ({tag.count})
													</Chip>
												))}
											</div>
										) : (
											<p className="text-gray-500 text-center py-4">
												No tags yet
											</p>
										)}
									</CardBody>
								</Card>
							</div>

							{/* Quick Actions */}
							<Card className="shadow-lg">
								<CardHeader className="pb-3">
									<h3 className="text-lg font-semibold">Quick Actions</h3>
								</CardHeader>
								<Divider />
								<CardBody className="pt-4">
									<div className="flex flex-wrap gap-3">
										<Button
											color="primary"
											variant="flat"
											onPress={() => router.push("/videos")}
											radius="md"
											size="md"
										>
											View All Videos
										</Button>
										<Button
											color="secondary"
											variant="flat"
											onPress={() => router.push("/playlists")}
											radius="md"
											size="md"
										>
											View Playlists
										</Button>
										<Button
											color="success"
											variant="flat"
											onPress={() => router.push("/videos?categorized=false")}
											radius="md"
											size="md"
										>
											View Uncategorized
										</Button>
										{stats && stats.uncategorized > 0 && (
											<Button
												color="warning"
												variant="solid"
												onPress={handleBatchCategorize}
												isLoading={batchCategorizing}
												radius="md"
												size="md"
											>
												Categorize All ({stats.uncategorized})
											</Button>
										)}
									</div>
								</CardBody>
							</Card>
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
