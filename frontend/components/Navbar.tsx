"use client";

import {
  Navbar as HeroNavbar,
  NavbarBrand,
  NavbarContent,
  NavbarItem,
  Link as HeroLink,
  Button,
  Dropdown,
  DropdownTrigger,
  DropdownMenu,
  DropdownItem,
  Avatar,
} from "@heroui/react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import DashboardIcon from "@mui/icons-material/Dashboard";
import VideoLibraryIcon from "@mui/icons-material/VideoLibrary";
import PlaylistPlayIcon from "@mui/icons-material/PlaylistPlay";
import SmartDisplayIcon from "@mui/icons-material/SmartDisplay";

export default function Navbar() {
  const router = useRouter();
  const pathname = usePathname();
  const { user, clearAuth } = useAuthStore();

  const handleLogout = () => {
    clearAuth();
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    router.push("/");
  };

  const isActive = (path: string) => pathname === path;

  return (
    <HeroNavbar
      isBordered
      isBlurred
      className="bg-gray-900/95"
      maxWidth="xl"
    >
      <NavbarBrand>
        <Link href="/dashboard" className="font-bold text-xl text-white flex items-center gap-2">
          <SmartDisplayIcon />
          YouTube Manager
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
          <DropdownMenu aria-label="Profile Actions" variant="flat">
            <DropdownItem key="profile" className="h-14 gap-2">
              <p className="font-semibold">Signed in as</p>
              <p className="font-semibold">{user?.email}</p>
            </DropdownItem>
            <DropdownItem key="settings">Settings</DropdownItem>
            <DropdownItem key="help">Help & Feedback</DropdownItem>
            <DropdownItem key="logout" color="danger" onPress={handleLogout}>
              Log Out
            </DropdownItem>
          </DropdownMenu>
        </Dropdown>
      </NavbarContent>
    </HeroNavbar>
  );
}
