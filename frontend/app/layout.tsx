import type { Metadata } from "next";
import { DM_Mono, DM_Sans, Syne } from "next/font/google";
import { preconnect } from "react-dom";
import "./globals.css";
import { Providers } from "./providers";

const syne = Syne({
	subsets: ["latin"],
	weight: "variable",
	variable: "--font-syne",
	display: "swap",
});

const dmSans = DM_Sans({
	subsets: ["latin"],
	weight: "variable",
	variable: "--font-dm-sans",
	display: "swap",
});

const dmMono = DM_Mono({
	subsets: ["latin"],
	weight: ["300", "400", "500"],
	variable: "--font-dm-mono",
	display: "swap",
});

export const metadata: Metadata = {
	title: {
		default: "YouTube Manager - AI-Powered Video Organization",
		template: "%s | YouTube Manager",
	},
	description:
		"Manage and organize your YouTube liked videos and playlists with AI-powered categorization",
	icons: {
		icon: "/favicon.svg",
		apple: "/favicon.svg",
	},
};

export default function RootLayout({
	children,
}: Readonly<{
	children: React.ReactNode;
}>) {
	preconnect("https://fonts.googleapis.com");
	preconnect("https://fonts.gstatic.com", { crossOrigin: "anonymous" });
	return (
		<html lang="en" suppressHydrationWarning>
			<body
				className={`${syne.variable} ${dmSans.variable} ${dmMono.variable}`}
			>
				<Providers>{children}</Providers>
			</body>
		</html>
	);
}
