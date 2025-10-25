import { heroui } from "@heroui/react";
import type { Config } from "tailwindcss";

const config: Config = {
	content: [
		"./pages/**/*.{js,ts,jsx,tsx,mdx}",
		"./components/**/*.{js,ts,jsx,tsx,mdx}",
		"./app/**/*.{js,ts,jsx,tsx,mdx}",
		"./node_modules/@heroui/theme/dist/**/*.{js,ts,jsx,tsx}",
	],
	theme: {
		extend: {
			colors: {
				background: "var(--background)",
				foreground: "var(--foreground)",
			},
			fontFamily: {
				jost: ["var(--font-jost)", "sans-serif"],
				"work-sans": ["var(--font-work-sans)", "sans-serif"],
				"red-hat": ["var(--font-red-hat)", "sans-serif"],
				alata: ["var(--font-alata)", "sans-serif"],
			},
		},
	},
	darkMode: "class",
	plugins: [heroui()],
};

export default config;
