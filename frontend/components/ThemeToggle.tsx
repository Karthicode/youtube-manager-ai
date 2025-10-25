"use client";

import { Button } from "@heroui/react";
import DarkModeIcon from "@mui/icons-material/DarkMode";
import LightModeIcon from "@mui/icons-material/LightMode";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

export default function ThemeToggle() {
	const [mounted, setMounted] = useState(false);
	const { theme, setTheme } = useTheme();

	// Handle hydration - avoid mismatch between server and client
	useEffect(() => {
		setMounted(true);
	}, []);

	// Don't render anything until mounted to avoid hydration mismatch
	if (!mounted) {
		return null;
	}

	const isDark = theme === "dark";

	return (
		<Button
			isIconOnly
			variant="light"
			onPress={() => setTheme(isDark ? "light" : "dark")}
			aria-label={`Switch to ${isDark ? "light" : "dark"} mode`}
			title={`Switch to ${isDark ? "light" : "dark"} mode`}
		>
			{isDark ? (
				<LightModeIcon className="text-yellow-400" />
			) : (
				<DarkModeIcon className="text-gray-700 dark:text-gray-300" />
			)}
		</Button>
	);
}
