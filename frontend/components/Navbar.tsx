"use client";

import {
	Avatar,
	Dropdown,
	DropdownItem,
	DropdownMenu,
	DropdownTrigger,
	Navbar as HeroNavbar,
	NavbarBrand,
	NavbarContent,
	NavbarItem,
	NavbarMenu,
	NavbarMenuItem,
	NavbarMenuToggle,
} from "@heroui/react";
import ChatIcon from "@mui/icons-material/Chat";
import DashboardIcon from "@mui/icons-material/Dashboard";
import InsightsIcon from "@mui/icons-material/Insights";
import PlaylistPlayIcon from "@mui/icons-material/PlaylistPlay";
import SmartDisplayIcon from "@mui/icons-material/SmartDisplay";
import VideoLibraryIcon from "@mui/icons-material/VideoLibrary";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import React from "react";
import { deleteCookie } from "@/lib/cookies";
import { useAuthStore } from "@/store/auth";
import ThemeToggle from "./ThemeToggle";

export default function Navbar() {
	const router = useRouter();
	const pathname = usePathname();
	const { user, clearAuth } = useAuthStore();
	const displayEmail =
		user?.email && !user.email.endsWith("@youtube.user")
			? user.email
			: "Email unavailable";
	const [isMenuOpen, setIsMenuOpen] = React.useState(false);

	const handleLogout = () => {
		clearAuth();
		localStorage.removeItem("access_token");
		localStorage.removeItem("refresh_token");
		deleteCookie("is_authenticated");
		router.push("/");
	};

	const isActive = (path: string) => pathname === path;

	const menuItems = [
		{ label: "Dashboard", path: "/dashboard", icon: <DashboardIcon /> },
		{ label: "Insights", path: "/insights", icon: <InsightsIcon /> },
		{ label: "Liked Videos", path: "/videos", icon: <VideoLibraryIcon /> },
		{ label: "Playlists", path: "/playlists", icon: <PlaylistPlayIcon /> },
		{ label: "Chat", path: "/chat", icon: <ChatIcon /> },
	];

	return (
		<HeroNavbar
			isBlurred
			className="border-b border-border bg-background/85 backdrop-blur-xl"
			maxWidth="xl"
			isMenuOpen={isMenuOpen}
			onMenuOpenChange={setIsMenuOpen}
		>
			<NavbarContent className="sm:hidden" justify="start">
				<NavbarMenuToggle
					aria-label={isMenuOpen ? "Close menu" : "Open menu"}
				/>
			</NavbarContent>

			<NavbarBrand>
				<Link
					href="/dashboard"
					className="font-display font-bold text-xl tracking-tight text-text-primary flex items-center gap-2 py-1"
				>
					<SmartDisplayIcon
						sx={{ fontSize: { xs: 24, sm: 28 }, color: "#E63946" }}
					/>
					<span className="hidden xs:inline">YouTube Manager</span>
					<span className="xs:hidden">YT Manager</span>
				</Link>
			</NavbarBrand>

			<NavbarContent className="hidden sm:flex gap-8" justify="center">
				{menuItems.map((item) => (
					<NavbarItem key={item.path} isActive={isActive(item.path)}>
						<Link
							href={item.path}
							className={`flex items-center gap-2 px-2 transition-colors ${
								isActive(item.path)
									? "text-text-primary nav-link-active"
									: "text-text-secondary hover:text-text-primary"
							}`}
						>
							{React.cloneElement(
								item.icon as React.ReactElement<{ sx?: object }>,
								{ sx: { fontSize: 18 } },
							)}
							<span>{item.label}</span>
						</Link>
					</NavbarItem>
				))}
			</NavbarContent>

			<NavbarContent justify="end">
				<NavbarItem>
					<ThemeToggle />
				</NavbarItem>
				<Dropdown placement="bottom-end">
					<DropdownTrigger>
						<Avatar
							isBordered
							as="button"
							className="transition-transform"
							color="primary"
							name={user?.name}
							size="sm"
							src={user?.picture || undefined}
						/>
					</DropdownTrigger>
					<DropdownMenu
						aria-label="Profile Actions"
						variant="flat"
						onAction={(key) => {
							if (key === "logout") {
								handleLogout();
							}
						}}
					>
						<DropdownItem key="profile" className="h-14 gap-2" isReadOnly>
							<p className="font-semibold">Signed in as</p>
							<p className="font-semibold">{displayEmail}</p>
						</DropdownItem>
						<DropdownItem key="settings" as={Link} href="/settings">
							Settings
						</DropdownItem>
						<DropdownItem key="help" as={Link} href="/help">
							Help & Feedback
						</DropdownItem>
						<DropdownItem key="logout" color="danger">
							Log Out
						</DropdownItem>
					</DropdownMenu>
				</Dropdown>
			</NavbarContent>

			<NavbarMenu className="bg-background">
				{menuItems.map((item, index) => (
					<NavbarMenuItem key={`${item.label}-${index}`}>
						<Link
							className={`w-full flex items-center gap-3 py-2 transition-colors ${
								isActive(item.path)
									? "text-text-primary font-semibold"
									: "text-text-secondary"
							}`}
							href={item.path}
							onClick={() => setIsMenuOpen(false)}
						>
							{item.icon}
							{item.label}
						</Link>
					</NavbarMenuItem>
				))}
			</NavbarMenu>
		</HeroNavbar>
	);
}
