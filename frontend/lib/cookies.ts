/**
 * Set a cookie with the given name, value, and options.
 */
export function setCookie(name: string, value: string, maxAge: number): void {
	if ("cookieStore" in window) {
		(window.cookieStore as CookieStore).set({
			name,
			value,
			path: "/",
			maxAge,
			sameSite: "lax",
		});
	} else {
		// biome-ignore lint/suspicious/noDocumentCookie: fallback for browsers without Cookie Store API
		document.cookie = `${name}=${value}; path=/; max-age=${maxAge}; SameSite=Lax`;
	}
}

/**
 * Delete a cookie by name.
 */
export function deleteCookie(name: string): void {
	if ("cookieStore" in window) {
		(window.cookieStore as CookieStore).delete(name);
	} else {
		// biome-ignore lint/suspicious/noDocumentCookie: fallback for browsers without Cookie Store API
		document.cookie = `${name}=; path=/; max-age=0; SameSite=Lax`;
	}
}

interface CookieStore {
	set(options: {
		name: string;
		value: string;
		path?: string;
		maxAge?: number;
		sameSite?: "strict" | "lax" | "none";
	}): Promise<void>;
	delete(name: string): Promise<void>;
}
