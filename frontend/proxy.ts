import { type NextRequest, NextResponse } from "next/server";

const PROTECTED_ROUTES = [
	"/dashboard",
	"/videos",
	"/playlists",
	"/insights",
	"/settings",
	"/help",
];

export function proxy(request: NextRequest) {
	const { pathname } = request.nextUrl;
	const isAuthenticated = request.cookies.get("is_authenticated")?.value;

	// Redirect unauthenticated users away from protected routes
	const isProtected = PROTECTED_ROUTES.some(
		(route) => pathname === route || pathname.startsWith(`${route}/`),
	);

	if (isProtected && !isAuthenticated) {
		return NextResponse.redirect(new URL("/", request.url));
	}

	// Redirect authenticated users away from the login page
	if (pathname === "/" && isAuthenticated) {
		return NextResponse.redirect(new URL("/dashboard", request.url));
	}

	return NextResponse.next();
}

export const config = {
	matcher: [
		"/",
		"/dashboard/:path*",
		"/videos/:path*",
		"/playlists/:path*",
		"/insights/:path*",
		"/settings/:path*",
		"/help/:path*",
	],
};
