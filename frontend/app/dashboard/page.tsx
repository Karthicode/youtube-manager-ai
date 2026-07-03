"use client";

import {
	Button,
	Modal,
	ModalBody,
	ModalContent,
	ModalFooter,
	ModalHeader,
	Spinner,
} from "@heroui/react";
import { useRouter } from "next/navigation";
import { Suspense, useState } from "react";
import { mutate } from "swr";
import { videosApi } from "@/api/api";
import CategorizationProgressSSE from "@/components/CategorizationProgressSSE";
import ContinueWatching from "@/components/ContinueWatching";
import DashboardStats from "@/components/DashboardStats";
import DashboardStatsSkeleton from "@/components/DashboardStatsSkeleton";
import LibraryStatusStrip from "@/components/LibraryStatusStrip";
import Navbar from "@/components/Navbar";
import { useAuthGuard } from "@/hooks";
import { swrKeys } from "@/lib/swrKeys";

export default function Dashboard() {
	const router = useRouter();
	const { isReady, isAuthenticated, user } = useAuthGuard();
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
						</div>
					</div>

					{/* Auto-categorize status banner (failure / stale) */}
					<LibraryStatusStrip
						lastSyncAt={user?.last_sync_at ?? null}
						onJobComplete={refreshStats}
					/>

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

					<Suspense fallback={<DashboardStatsSkeleton />}>
						<DashboardStats
							batchCategorizing={batchCategorizing}
							onBatchCategorize={handleBatchCategorize}
							onCategoryClick={handleCategoryClick}
						/>
					</Suspense>
				</div>
			</div>
		</div>
	);
}
