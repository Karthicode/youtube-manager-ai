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
				surface: "var(--surface)",
				"surface-elevated": "var(--surface-elevated)",
				border: "var(--border)",
				"accent-red": "var(--accent-red)",
				"accent-blue": "var(--accent-blue)",
				"accent-cyan": "var(--accent-cyan)",
				"accent-amber": "var(--accent-amber)",
				success: "var(--success)",
				"text-primary": "var(--text-primary)",
				"text-secondary": "var(--text-secondary)",
			},
			fontFamily: {
				sans: ["var(--font-dm-sans)", "system-ui", "sans-serif"],
				display: ["var(--font-syne)", "system-ui", "sans-serif"],
				mono: ["var(--font-dm-mono)", "ui-monospace", "monospace"],
			},
		},
	},
	darkMode: "class",
	plugins: [
		heroui({
			defaultTheme: "dark",
			themes: {
				dark: {
					colors: {
						background: "#08080C",
						foreground: "#F2F2F7",
						divider: "#1E1E2A",
						focus: "#E63946",
						content1: "#0F0F14",
						content2: "#16161E",
						content3: "#1E1E2A",
						content4: "#2A2A38",
						primary: {
							50: "#fef2f3",
							100: "#fde6e7",
							200: "#fbd0d3",
							300: "#f7aab0",
							400: "#f17680",
							500: "#e63946",
							600: "#d4202e",
							700: "#b21824",
							800: "#941722",
							900: "#7c1922",
							DEFAULT: "#E63946",
							foreground: "#FFFFFF",
						},
						secondary: {
							DEFAULT: "#06B6D4",
							foreground: "#FFFFFF",
						},
					},
				},
				light: {
					colors: {
						background: "#FAFAF8",
						foreground: "#09090B",
						divider: "#E4E4E7",
						focus: "#E63946",
						content1: "#FFFFFF",
						content2: "#F4F4F5",
						content3: "#E4E4E7",
						content4: "#D4D4D8",
						primary: {
							50: "#fef2f3",
							100: "#fde6e7",
							200: "#fbd0d3",
							300: "#f7aab0",
							400: "#f17680",
							500: "#e63946",
							600: "#d4202e",
							700: "#b21824",
							800: "#941722",
							900: "#7c1922",
							DEFAULT: "#E63946",
							foreground: "#FFFFFF",
						},
						secondary: {
							DEFAULT: "#06B6D4",
							foreground: "#FFFFFF",
						},
					},
				},
			},
		}),
	],
};

export default config;
