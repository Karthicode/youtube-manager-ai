"use client";

import GoogleIcon from "@mui/icons-material/Google";
import SmartDisplayIcon from "@mui/icons-material/SmartDisplay";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { authApi } from "@/api/api";
import { setCookie } from "@/lib/cookies";
import { useAuthStore } from "@/store/auth";

export default function Home() {
	const router = useRouter();
	const { isAuthenticated, isHydrated } = useAuthStore();

	useEffect(() => {
		if (!isHydrated) return;

		if (isAuthenticated) {
			// Ensure the middleware cookie is set before navigating. This fixes
			// the case where tokens exist in localStorage but the cookie has
			// expired, which causes an infinite middleware redirect loop.
			setCookie("is_authenticated", "true", 604800);
			router.push("/dashboard");
		}
	}, [isAuthenticated, isHydrated, router]);

	// Show loading state until hydration completes
	if (!isHydrated) {
		return (
			<div className="min-h-screen bg-[#08080C] flex items-center justify-center">
				<div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#E63946]" />
			</div>
		);
	}

	// If authenticated, don't render login UI (redirect will happen)
	if (isAuthenticated) {
		return (
			<div className="min-h-screen bg-[#08080C] flex items-center justify-center">
				<div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#E63946]" />
			</div>
		);
	}

	const handleLogin = async () => {
		try {
			const response = await authApi.getLoginUrl(window.location.origin);
			window.location.href = response.data.auth_url;
		} catch {
			alert("Failed to start login. Please try again.");
		}
	};

	return (
		<div className="flex flex-col lg:flex-row h-screen overflow-hidden">
			{/* Left Panel — Editorial */}
			<div className="hidden lg:flex lg:w-3/5 relative bg-[#08080C] flex-col justify-between p-12 noise-overlay overflow-hidden">
				{/* Dot grid */}
				<div className="absolute inset-0 dot-grid opacity-60" />

				{/* Red top accent line */}
				<div className="absolute top-0 left-0 right-0 h-[2px] bg-[#E63946]" />

				{/* Content */}
				<div className="relative z-10">
					<div className="flex items-center gap-2 text-[#6B6B7E]">
						<SmartDisplayIcon sx={{ fontSize: 20, color: "#E63946" }} />
						<span className="text-sm font-mono-editorial tracking-widest uppercase">
							YouTube Manager AI
						</span>
					</div>
				</div>

				<div className="relative z-10 space-y-6">
					<h1 className="font-display text-5xl xl:text-7xl font-bold leading-[1.05] tracking-tight text-[#F2F2F7]">
						Your library. <span className="text-[#E63946]">Organized</span>
						<br />
						by AI.
					</h1>
					<p className="text-[#6B6B7E] text-lg max-w-md leading-relaxed">
						Automatically categorize, tag, and explore your liked videos with
						the power of large language models.
					</p>
				</div>

				<div className="relative z-10">
					<div className="flex items-center gap-6 text-[#6B6B7E]">
						{["AI CATEGORIZATION", "SMART PLAYLISTS", "ANALYTICS"].map(
							(label, i) => (
								<span key={label} className="flex items-center gap-6">
									<span className="text-[10px] font-mono-editorial tracking-[0.15em] uppercase">
										{label}
									</span>
									{i < 2 && (
										<span className="text-[#2A2A38]" aria-hidden>
											·
										</span>
									)}
								</span>
							),
						)}
					</div>
				</div>
			</div>

			{/* Right Panel — Sign In */}
			<div className="w-full lg:w-2/5 flex items-center justify-center p-8 bg-[#0F0F14]">
				<motion.div
					initial={{ opacity: 0, y: 16 }}
					animate={{ opacity: 1, y: 0 }}
					transition={{ duration: 0.5, ease: "easeOut" }}
					className="w-full max-w-sm space-y-10"
				>
					{/* Mobile brand */}
					<div className="flex lg:hidden items-center gap-2 justify-center">
						<SmartDisplayIcon sx={{ fontSize: 24, color: "#E63946" }} />
						<span className="font-display font-bold text-xl text-[#F2F2F7]">
							YouTube Manager AI
						</span>
					</div>

					<div className="space-y-2">
						<h2 className="font-display text-3xl font-bold text-[#F2F2F7] tracking-tight">
							Sign in
						</h2>
						<p className="text-[#6B6B7E] text-sm">
							Connect your Google account to get started.
						</p>
					</div>

					<button
						type="button"
						onClick={handleLogin}
						className="w-full flex items-center justify-center gap-3 px-6 py-3.5 bg-[#16161E] border border-[#1E1E2A] hover:border-[#E63946] text-[#F2F2F7] font-medium rounded-xl transition-all duration-200 hover:bg-[#1E1E2A]"
					>
						<GoogleIcon sx={{ fontSize: 20 }} />
						<span>Continue with Google</span>
					</button>

					<p className="text-center text-xs text-[#6B6B7E]">
						By continuing, you agree to our Terms of Service and Privacy Policy.
						<br />
						<span className="text-[#2A2A38]">Secured by OAuth 2.0</span>
					</p>
				</motion.div>
			</div>
		</div>
	);
}
