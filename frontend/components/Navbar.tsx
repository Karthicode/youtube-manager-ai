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
import DashboardIcon from "@mui/icons-material/Dashboard";
import PlaylistPlayIcon from "@mui/icons-material/PlaylistPlay";
import SmartDisplayIcon from "@mui/icons-material/SmartDisplay";
import VideoLibraryIcon from "@mui/icons-material/VideoLibrary";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import React from "react";
import { useAuthStore } from "@/store/auth";
import ThemeToggle from "./ThemeToggle";

export default function Navbar() {
	const router = useRouter();
	const pathname = usePathname();
	const { user, clearAuth } = useAuthStore();
	const [isMenuOpen, setIsMenuOpen] = React.useState(false);

	const handleLogout = () => {
		clearAuth();
		localStorage.removeItem("access_token");
		localStorage.removeItem("refresh_token");
		router.push("/");
	};

	const isActive = (path: string) => pathname === path;

	const menuItems = [
		{ label: "Dashboard", path: "/dashboard", icon: <DashboardIcon /> },
		{ label: "Liked Videos", path: "/videos", icon: <VideoLibraryIcon /> },
		{ label: "Playlists", path: "/playlists", icon: <PlaylistPlayIcon /> },
	];

	return (
		<HeroNavbar
			isBordered
			isBlurred
			className="bg-white/95 dark:bg-gray-900/95"
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
					className="font-bold text-base sm:text-xl text-gray-900 dark:text-white flex items-center gap-2"
				>
					<SmartDisplayIcon sx={{ fontSize: { xs: 24, sm: 28 } }} />
					<span className="hidden xs:inline">YouTube Manager</span>
					<span className="xs:hidden">YT Manager</span>
				</Link>
			</NavbarBrand>

			<NavbarContent className="hidden sm:flex gap-8" justify="center">
				<NavbarItem isActive={isActive("/dashboard")}>
					<Link
						href="/dashboard"
						className={`flex items-center gap-2 px-2 ${
							isActive("/dashboard")
								? "text-primary font-medium"
								: "text-foreground font-medium hover:text-primary transition-colors"
						}`}
					>
						<DashboardIcon fontSize="small" />
						<span>Dashboard</span>
					</Link>
				</NavbarItem>
				<NavbarItem isActive={isActive("/videos")}>
					<Link
						href="/videos"
						className={`flex items-center gap-2 px-2 ${
							isActive("/videos")
								? "text-primary font-medium"
								: "text-foreground font-medium hover:text-primary transition-colors"
						}`}
					>
						<VideoLibraryIcon fontSize="small" />
						<span>Liked Videos</span>
					</Link>
				</NavbarItem>
				<NavbarItem isActive={isActive("/playlists")}>
					<Link
						href="/playlists"
						className={`flex items-center gap-2 px-2 ${
							isActive("/playlists")
								? "text-primary font-medium"
								: "text-foreground font-medium hover:text-primary transition-colors"
						}`}
					>
						<PlaylistPlayIcon fontSize="small" />
						<span>Playlists</span>
					</Link>
				</NavbarItem>
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
							if (key === "settings") {
								router.push("/settings");
							} else if (key === "help") {
								router.push("/help");
							} else if (key === "logout") {
								handleLogout();
							}
						}}
					>
						<DropdownItem key="profile" className="h-14 gap-2" isReadOnly>
							<p className="font-semibold">Signed in as</p>
							<p className="font-semibold">{user?.email}</p>
						</DropdownItem>
						<DropdownItem key="settings">Settings</DropdownItem>
						<DropdownItem key="help">Help & Feedback</DropdownItem>
						<DropdownItem key="logout" color="danger">
							Log Out
						</DropdownItem>
					</DropdownMenu>
				</Dropdown>
			</NavbarContent>

			<NavbarMenu>
				{menuItems.map((item, index) => (
					<NavbarMenuItem key={`${item.label}-${index}`}>
						<Link
							className={`w-full flex items-center gap-3 py-2 ${
								isActive(item.path)
									? "text-primary font-semibold"
									: "text-foreground"
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
