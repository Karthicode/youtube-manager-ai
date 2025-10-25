"use client";

import { Button, Card, CardBody } from "@heroui/react";
import AutoFixHighIcon from "@mui/icons-material/AutoFixHigh";
import BarChartIcon from "@mui/icons-material/BarChart";
import CategoryIcon from "@mui/icons-material/Category";
import GoogleIcon from "@mui/icons-material/Google";
import SearchIcon from "@mui/icons-material/Search";
import SmartDisplayIcon from "@mui/icons-material/SmartDisplay";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { authApi } from "@/api/api";
import { useAuthStore } from "@/store/auth";

export default function Home() {
	const router = useRouter();
	const { isAuthenticated } = useAuthStore();

	useEffect(() => {
		if (isAuthenticated) {
			router.push("/dashboard");
		}
	}, [isAuthenticated, router]);

	const handleLogin = async () => {
		try {
			const response = await authApi.getLoginUrl();
			window.location.href = response.data.auth_url;
		} catch (error) {
			console.error("Failed to get login URL:", error);
			const errorMessage =
				error instanceof Error ? error.message : "Unknown error";
			alert(
				`Login failed: ${errorMessage}\n\nPlease check the console for details.`,
			);
		}
	};

	return (
		<div className="flex flex-col md:flex-row min-h-screen">
			{/* Left Side - Sign In Form */}
			<div className="w-full md:w-1/2 flex items-center justify-center p-4 sm:p-6 md:p-8 bg-linear-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-950">
				<Card className="w-full max-w-md shadow-2xl">
					<CardBody className="p-6 sm:p-8 md:p-10">
						<div className="space-y-6 sm:space-y-8">
							{/* Header */}
							<div className="text-center space-y-2">
								<div className="flex justify-center mb-4">
									<div className="p-3 bg-gradient-to-br from-red-600 to-red-700 rounded-2xl shadow-lg">
										<SmartDisplayIcon
											className="text-white"
											sx={{ fontSize: 40 }}
										/>
									</div>
								</div>
								<h1 className="text-2xl sm:text-3xl font-bold bg-gradient-to-r from-red-600 to-red-700 bg-clip-text text-transparent">
									Welcome Back
								</h1>
								<p className="text-sm sm:text-base text-gray-600 dark:text-gray-400">
									Sign in to manage your YouTube videos with AI
								</p>
							</div>

							{/* Buttons */}
							<div className="space-y-4">
								<Button
									size="lg"
									className="w-full bg-white dark:bg-gray-800 border-2 border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 font-semibold shadow-md hover:shadow-lg transition-all"
									onPress={handleLogin}
									startContent={<GoogleIcon />}
								>
									Continue with Google
								</Button>
							</div>

							{/* Footer */}
							<div className="text-center space-y-4">
								<p className="text-xs text-gray-500 dark:text-gray-400">
									By continuing, you agree to our Terms of Service and Privacy
									Policy
								</p>
								<div className="flex items-center justify-center gap-2 text-xs text-gray-400">
									<span>Secured by</span>
									<span className="font-semibold text-blue-600">OAuth 2.0</span>
								</div>
							</div>
						</div>
					</CardBody>
				</Card>
			</div>

			{/* Right Side - Feature Showcase */}
			<div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-black via-gray-900 to-red-950 relative overflow-hidden p-4">
				<div className="w-full bg-gradient-to-br from-red-600 to-black rounded-3xl relative overflow-hidden">
					{/* Animated Background Pattern */}
					<div className="absolute inset-0 opacity-10">
						<div className="absolute top-0 left-0 w-96 h-96 bg-red-500 rounded-full blur-3xl animate-pulse" />
						<div className="absolute bottom-0 right-0 w-96 h-96 bg-red-500 rounded-full blur-3xl animate-pulse animation-delay-2000" />
					</div>

					<div className="relative z-10 flex flex-col justify-between p-8 lg:p-12 xl:p-16 text-white w-full">
						{/* Header */}
						<div className="space-y-4 lg:space-y-6">
							<div className="inline-block">
								<div className="flex items-center gap-2 lg:gap-3 bg-red-600/90 backdrop-blur-sm px-3 lg:px-4 py-2 rounded-full shadow-lg">
									<SmartDisplayIcon sx={{ fontSize: { lg: 24, xl: 28 } }} />
									<span className="font-bold text-base lg:text-lg">
										YouTube Manager AI
									</span>
								</div>
							</div>

							<h2 className="text-3xl lg:text-5xl xl:text-6xl font-bold leading-tight">
								Organize Your
								<br />
								YouTube Library
								<br />
								<span className="text-red-300">with AI Magic</span>
							</h2>

							<p className="text-base lg:text-xl text-white/90 max-w-lg">
								Automatically categorize, tag, and organize your liked videos
								and playlists with the power of artificial intelligence.
							</p>
						</div>

						{/* Features */}
						<div className="space-y-4 lg:space-y-6">
							<div className="grid grid-cols-1 gap-3 lg:gap-4">
								<div className="flex items-center gap-3 lg:gap-4 bg-black/40 backdrop-blur-sm p-3 lg:p-4 rounded-xl border border-red-500/30 hover:bg-red-500/20 transition-all">
									<div className="p-2 lg:p-3 bg-red-600/80 rounded-lg">
										<AutoFixHighIcon sx={{ fontSize: 28 }} />
									</div>
									<div>
										<p className="font-semibold text-base lg:text-lg">
											AI-Powered Categorization
										</p>
										<p className="text-white/80 text-xs lg:text-sm">
											Smart categorization using GPT-4
										</p>
									</div>
								</div>

								<div className="flex items-center gap-3 lg:gap-4 bg-black/40 backdrop-blur-sm p-3 lg:p-4 rounded-xl border border-red-500/30 hover:bg-red-500/20 transition-all">
									<div className="p-2 lg:p-3 bg-red-600/80 rounded-lg">
										<CategoryIcon sx={{ fontSize: 28 }} />
									</div>
									<div>
										<p className="font-semibold text-base lg:text-lg">
											Smart Organization
										</p>
										<p className="text-white/80 text-xs lg:text-sm">
											Intelligent tags and categories
										</p>
									</div>
								</div>

								<div className="flex items-center gap-3 lg:gap-4 bg-black/40 backdrop-blur-sm p-3 lg:p-4 rounded-xl border border-red-500/30 hover:bg-red-500/20 transition-all">
									<div className="p-2 lg:p-3 bg-red-600/80 rounded-lg">
										<SearchIcon sx={{ fontSize: 28 }} />
									</div>
									<div>
										<p className="font-semibold text-base lg:text-lg">
											Advanced Search
										</p>
										<p className="text-white/80 text-xs lg:text-sm">
											Find any video instantly
										</p>
									</div>
								</div>

								<div className="flex items-center gap-3 lg:gap-4 bg-black/40 backdrop-blur-sm p-3 lg:p-4 rounded-xl border border-red-500/30 hover:bg-red-500/20 transition-all">
									<div className="p-2 lg:p-3 bg-red-600/80 rounded-lg">
										<BarChartIcon sx={{ fontSize: 28 }} />
									</div>
									<div>
										<p className="font-semibold text-base lg:text-lg">
											Analytics Dashboard
										</p>
										<p className="text-white/80 text-xs lg:text-sm">
											Track your viewing patterns
										</p>
									</div>
								</div>
							</div>
						</div>

						{/* Footer */}
						<div className="flex items-center justify-between text-sm text-white/60">
							<p>© 2025 YouTube Manager AI</p>
							<div className="flex gap-4">
								<button
									type="button"
									className="hover:text-white transition-colors"
									onClick={() => {
										/* Privacy policy handler */
									}}
								>
									Privacy
								</button>
								<button
									type="button"
									className="hover:text-white transition-colors"
									onClick={() => {
										/* Terms handler */
									}}
								>
									Terms
								</button>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	);
}
