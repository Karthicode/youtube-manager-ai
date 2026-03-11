"use client";

import { HeroUIProvider } from "@heroui/react";
import { ThemeProvider as NextThemesProvider } from "next-themes";
import { SWRConfig } from "swr";
import { api } from "@/api/api";
import GlobalMiniPlayer from "@/components/player/GlobalMiniPlayer";

const swrFetcher = (url: string) => api.get(url).then((res) => res.data);

export function Providers({ children }: { children: React.ReactNode }) {
	return (
		<SWRConfig
			value={{
				fetcher: swrFetcher,
				revalidateOnFocus: false,
				revalidateOnReconnect: true,
				shouldRetryOnError: false,
				dedupingInterval: 2000,
			}}
		>
			<HeroUIProvider>
				<NextThemesProvider attribute="class" defaultTheme="dark">
					{children}
					<GlobalMiniPlayer />
				</NextThemesProvider>
			</HeroUIProvider>
		</SWRConfig>
	);
}
