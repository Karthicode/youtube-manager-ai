import type { Metadata } from "next";

export const metadata: Metadata = {
	title: "Playlists",
};

export default function PlaylistsLayout({
	children,
}: {
	children: React.ReactNode;
}) {
	return children;
}
