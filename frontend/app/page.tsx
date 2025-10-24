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
			const errorMessage = error instanceof Error ? error.message : "Unknown error";
			alert(
				`Login failed: ${errorMessage}\n\nPlease check the console for details.`,
			);
		}
	};

	return (
		<div className="flex min-h-screen">
			{/* Left Side - Sign In Form */}
			<div className="w-full md:w-1/2 flex items-center justify-center p-8 bg-linear-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-950">
				<Card className="w-full max-w-md shadow-2xl">
					<CardBody className="p-10">
						<div className="space-y-8">
							{/* Header */}
							<div className="text-center space-y-2">
								<div className="flex justify-center mb-4">
									<div className="p-3 bg-linear-to-br from-blue-600 to-purple-600 rounded-2xl">
										<SmartDisplayIcon
											className="text-white"
											sx={{ fontSize: 40 }}
										/>
									</div>
								</div>
								<h1 className="text-3xl font-bold bg-linear-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
									Welcome Back
								</h1>
								<p className="text-gray-600 dark:text-gray-400">
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

								<div className="relative">
									<div className="absolute inset-0 flex items-center">
										<div className="w-full border-t border-gray-300 dark:border-gray-700" />
									</div>
									<div className="relative flex justify-center text-sm">
										<span className="px-4 bg-white dark:bg-gray-800 text-gray-500 font-medium">
											OR
										</span>
									</div>
								</div>

								<Button
									size="lg"
									className="w-full bg-linear-to-r from-blue-600 via-purple-600 to-pink-600 text-white font-semibold shadow-lg hover:shadow-xl hover:scale-[1.02] transition-all"
									onPress={handleLogin}
									startContent={<SmartDisplayIcon />}
								>
									Continue with YouTube
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
			<div className="hidden md:flex md:w-1/2 bg-linear-to-br from-blue-600 via-purple-600 to-pink-600 relative overflow-hidden">
				{/* Animated Background Pattern */}
				<div className="absolute inset-0 opacity-10">
					<div className="absolute top-0 left-0 w-96 h-96 bg-white rounded-full blur-3xl animate-pulse" />
					<div className="absolute bottom-0 right-0 w-96 h-96 bg-white rounded-full blur-3xl animate-pulse animation-delay-2000" />
				</div>

				<div className="relative z-10 flex flex-col justify-between p-12 lg:p-16 text-white w-full">
					{/* Header */}
					<div className="space-y-6">
						<div className="inline-block">
							<div className="flex items-center gap-3 bg-white/20 backdrop-blur-sm px-4 py-2 rounded-full">
								<SmartDisplayIcon />
								<span className="font-bold text-lg">YouTube Manager AI</span>
							</div>
						</div>

						<h2 className="text-5xl lg:text-6xl font-bold leading-tight">
							Organize Your
							<br />
							YouTube Library
							<br />
							<span className="text-blue-200">with AI Magic</span>
						</h2>

						<p className="text-xl text-white/90 max-w-lg">
							Automatically categorize, tag, and organize your liked videos and
							playlists with the power of artificial intelligence.
						</p>
					</div>

					{/* Features */}
					<div className="space-y-6">
						<div className="grid grid-cols-1 gap-4">
							<div className="flex items-center gap-4 bg-white/10 backdrop-blur-sm p-4 rounded-xl border border-white/20 hover:bg-white/20 transition-all">
								<div className="p-3 bg-white/20 rounded-lg">
									<AutoFixHighIcon sx={{ fontSize: 28 }} />
								</div>
								<div>
									<p className="font-semibold text-lg">
										AI-Powered Categorization
									</p>
									<p className="text-white/80 text-sm">
										Smart categorization using GPT-4
									</p>
								</div>
							</div>

							<div className="flex items-center gap-4 bg-white/10 backdrop-blur-sm p-4 rounded-xl border border-white/20 hover:bg-white/20 transition-all">
								<div className="p-3 bg-white/20 rounded-lg">
									<CategoryIcon sx={{ fontSize: 28 }} />
								</div>
								<div>
									<p className="font-semibold text-lg">Smart Organization</p>
									<p className="text-white/80 text-sm">
										Intelligent tags and categories
									</p>
								</div>
							</div>

							<div className="flex items-center gap-4 bg-white/10 backdrop-blur-sm p-4 rounded-xl border border-white/20 hover:bg-white/20 transition-all">
								<div className="p-3 bg-white/20 rounded-lg">
									<SearchIcon sx={{ fontSize: 28 }} />
								</div>
								<div>
									<p className="font-semibold text-lg">Advanced Search</p>
									<p className="text-white/80 text-sm">
										Find any video instantly
									</p>
								</div>
							</div>

							<div className="flex items-center gap-4 bg-white/10 backdrop-blur-sm p-4 rounded-xl border border-white/20 hover:bg-white/20 transition-all">
								<div className="p-3 bg-white/20 rounded-lg">
									<BarChartIcon sx={{ fontSize: 28 }} />
								</div>
								<div>
									<p className="font-semibold text-lg">Analytics Dashboard</p>
									<p className="text-white/80 text-sm">
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
	);
}
