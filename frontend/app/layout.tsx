import type { Metadata } from "next";
import { Jost } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const jost = Jost({
	subsets: ["latin"],
	weight: ["100", "200", "300", "400", "500", "600", "700", "800", "900"],
	style: ["normal", "italic"],
	variable: "--font-jost",
});

export const metadata: Metadata = {
	title: "YouTube Manager - AI-Powered Video Organization",
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
	return (
		<html lang="en" suppressHydrationWarning>
			<head>
				<link rel="preconnect" href="https://fonts.googleapis.com" />
				<link
					rel="preconnect"
					href="https://fonts.gstatic.com"
					crossOrigin="anonymous"
				/>
				<link
					href="https://fonts.googleapis.com/css2?family=Alata&family=Jost:ital,wght@0,100..900;1,100..900&family=Red+Hat+Display:ital,wght@0,300..900;1,300..900&family=Work+Sans:ital,wght@0,100..900;1,100..900&display=swap"
					rel="stylesheet"
				/>
			</head>
			<body className={jost.className}>
				<Providers>{children}</Providers>
			</body>
		</html>
	);
}
