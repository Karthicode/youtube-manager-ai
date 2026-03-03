"use client";

import {
	Button,
	Card,
	CardBody,
	CardHeader,
	Divider,
	Spinner,
	Switch,
} from "@heroui/react";
import { useState } from "react";
import { videosApi } from "@/api/api";
import Navbar from "@/components/Navbar";
import ThemeToggle from "@/components/ThemeToggle";
import { useAuthGuard } from "@/hooks";

export default function Settings() {
	const { isReady, isAuthenticated, user } = useAuthGuard();
	const [isClearingData, setIsClearingData] = useState(false);
	const displayEmail =
		user?.email && !user.email.endsWith("@youtube.user")
			? user.email
			: "Email not available from YouTube";

	const handleClearData = async () => {
		const confirmed = confirm(
			"Clear all AI-generated categories and tags from your videos? Videos will remain in your library.",
		);
		if (!confirmed) return;

		setIsClearingData(true);
		try {
			const response = await videosApi.clearCategorizations();
			const {
				message,
				cleared_videos,
				removed_category_links,
				removed_tag_links,
			} = response.data;
			alert(
				`${message}\n\nVideos updated: ${cleared_videos}\nCategory links removed: ${removed_category_links}\nTag links removed: ${removed_tag_links}`,
			);
		} catch (error) {
			const axiosErr = error as { response?: { data?: { detail?: string } } };
			alert(
				axiosErr.response?.data?.detail ||
					"Failed to clear categorizations. Please try again.",
			);
		} finally {
			setIsClearingData(false);
		}
	};

	// Don't render anything until hydrated and authenticated
	if (!isReady || !isAuthenticated) {
		return (
			<div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
				<Spinner size="lg" />
			</div>
		);
	}

	return (
		<div className="min-h-screen bg-gray-50 dark:bg-gray-900">
			<Navbar />
			<div className="container mx-auto px-4 py-8 max-w-4xl">
				<div className="space-y-6">
					{/* Header */}
					<div>
						<h1 className="text-3xl font-bold">Settings</h1>
						<p className="text-gray-600 dark:text-gray-400 mt-1">
							Manage your account preferences and application settings
						</p>
					</div>

					{/* Account Information */}
					<Card>
						<CardHeader>
							<h2 className="text-xl font-semibold">Account Information</h2>
						</CardHeader>
						<Divider />
						<CardBody className="space-y-4">
							<div>
								<span className="text-sm font-medium text-gray-700 dark:text-gray-300 block">
									Name
								</span>
								<p className="text-base mt-1">{user?.name}</p>
							</div>
							<div>
								<span className="text-sm font-medium text-gray-700 dark:text-gray-300 block">
									Email
								</span>
								<p className="text-base mt-1">{displayEmail}</p>
							</div>
							<div>
								<span className="text-sm font-medium text-gray-700 dark:text-gray-300 block">
									YouTube Channel ID
								</span>
								<p className="text-base mt-1 font-mono text-sm">
									{user?.youtube_channel_id || "Not connected"}
								</p>
							</div>
						</CardBody>
					</Card>

					{/* Appearance */}
					<Card>
						<CardHeader>
							<h2 className="text-xl font-semibold">Appearance</h2>
						</CardHeader>
						<Divider />
						<CardBody className="space-y-4">
							<div className="flex items-center justify-between">
								<div>
									<p className="font-medium">Theme</p>
									<p className="text-sm text-gray-600 dark:text-gray-400">
										Choose your preferred theme or use system preference
									</p>
								</div>
								<ThemeToggle />
							</div>
						</CardBody>
					</Card>

					{/* AI Categorization */}
					<Card>
						<CardHeader>
							<h2 className="text-xl font-semibold">AI Categorization</h2>
						</CardHeader>
						<Divider />
						<CardBody className="space-y-4">
							<div className="flex items-center justify-between">
								<div>
									<p className="font-medium">Auto-categorize new videos</p>
									<p className="text-sm text-gray-600 dark:text-gray-400">
										Automatically categorize videos when syncing from YouTube
									</p>
								</div>
								<Switch defaultSelected aria-label="Auto-categorize videos" />
							</div>
							<div className="flex items-center justify-between">
								<div>
									<p className="font-medium">
										Use background categorization for large batches
									</p>
									<p className="text-sm text-gray-600 dark:text-gray-400">
										Process large batches in the background for better
										performance
									</p>
								</div>
								<Switch
									defaultSelected
									aria-label="Background categorization"
								/>
							</div>
						</CardBody>
					</Card>

					{/* Data & Privacy */}
					<Card>
						<CardHeader>
							<h2 className="text-xl font-semibold">Data & Privacy</h2>
						</CardHeader>
						<Divider />
						<CardBody className="space-y-4">
							<div>
								<p className="font-medium mb-2">Connected Services</p>
								<div className="bg-gray-100 dark:bg-gray-800 rounded-lg p-4">
									<div className="flex items-center justify-between">
										<div className="flex items-center gap-3">
											<div className="w-10 h-10 bg-red-500 rounded-full flex items-center justify-center text-white font-semibold">
												Y
											</div>
											<div>
												<p className="font-medium">YouTube</p>
												<p className="text-sm text-gray-600 dark:text-gray-400">
													Connected
												</p>
											</div>
										</div>
										<Button color="danger" variant="flat" size="sm">
											Disconnect
										</Button>
									</div>
								</div>
							</div>
						</CardBody>
					</Card>

					{/* Danger Zone */}
					<Card className="border-2 border-danger">
						<CardHeader>
							<h2 className="text-xl font-semibold text-danger">Danger Zone</h2>
						</CardHeader>
						<Divider />
						<CardBody className="space-y-4">
							<div className="flex items-center justify-between">
								<div>
									<p className="font-medium">Clear all categorizations</p>
									<p className="text-sm text-gray-600 dark:text-gray-400">
										Remove all AI-generated categories and tags (videos remain)
									</p>
								</div>
								<Button
									color="danger"
									variant="flat"
									size="sm"
									onPress={handleClearData}
									isLoading={isClearingData}
								>
									Clear Data
								</Button>
							</div>
							<div className="flex items-center justify-between">
								<div>
									<p className="font-medium">Delete account</p>
									<p className="text-sm text-gray-600 dark:text-gray-400">
										Permanently delete your account and all associated data
									</p>
								</div>
								<Button color="danger" variant="solid" size="sm">
									Delete Account
								</Button>
							</div>
						</CardBody>
					</Card>
				</div>
			</div>
		</div>
	);
}
