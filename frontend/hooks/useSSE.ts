"use client";

import { useEffect, useRef, useState } from "react";

interface UseSSEOptions {
	onMessage?: (data: any) => void;
	onError?: (error: Event) => void;
	onOpen?: () => void;
}

export function useSSE(url: string | null, options: UseSSEOptions = {}) {
	const [isConnected, setIsConnected] = useState(false);
	const eventSourceRef = useRef<EventSource | null>(null);

	useEffect(() => {
		if (!url) return;

		// Create EventSource
		const eventSource = new EventSource(url);
		eventSourceRef.current = eventSource;

		eventSource.onopen = () => {
			setIsConnected(true);
			options.onOpen?.();
		};

		eventSource.onmessage = (event) => {
			try {
				const data = JSON.parse(event.data);
				options.onMessage?.(data);
			} catch (error) {
				console.error("Failed to parse SSE message:", error);
			}
		};

		eventSource.onerror = (error) => {
			setIsConnected(false);
			options.onError?.(error);
			eventSource.close();
		};

		// Cleanup
		return () => {
			eventSource.close();
			setIsConnected(false);
		};
	}, [url, options.onMessage, options.onError, options.onOpen]);

	const close = () => {
		eventSourceRef.current?.close();
		setIsConnected(false);
	};

	return { isConnected, close };
}
