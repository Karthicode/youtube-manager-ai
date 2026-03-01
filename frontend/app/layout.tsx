import type { Metadata } from "next";
import { Jost } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const jost = Jost({
	subsets: ["latin"],
	weight: ["100", "200", "300", "400", "500", "600", "700", "800", "900"],
	style: ["normal", "italic"],
	variable: "--font-jost",
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
	return (
		<html lang="en" suppressHydrationWarning>
			<body className={jost.className}>
				<Providers>{children}</Providers>
			</body>
		</html>
	);
}
