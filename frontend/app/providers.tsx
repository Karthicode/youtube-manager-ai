"use client";

import { HeroUIProvider } from "@heroui/react";
import { ThemeProvider as NextThemesProvider } from "next-themes";
import GlobalMiniPlayer from "@/components/player/GlobalMiniPlayer";

export function Providers({ children }: { children: React.ReactNode }) {
	return (
		<HeroUIProvider>
			<NextThemesProvider attribute="class" defaultTheme="dark">
				{children}
				<GlobalMiniPlayer />
			</NextThemesProvider>
		</HeroUIProvider>
	);
}
