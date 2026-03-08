"use client";

import {
	Button,
	Card,
	CardBody,
	Chip,
	Input,
	ScrollShadow,
	Spinner,
} from "@heroui/react";
import AddIcon from "@mui/icons-material/Add";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import BuildIcon from "@mui/icons-material/Build";
import DeleteIcon from "@mui/icons-material/Delete";
import SendIcon from "@mui/icons-material/Send";
import { useCallback, useEffect, useRef, useState } from "react";
import { chatApi } from "@/api/api";
import Navbar from "@/components/Navbar";
import { useAuthGuard } from "@/hooks";
import type { ChatMessage, ChatSession } from "@/types";

const SUGGESTED_PROMPTS = [
	"What are my most liked topics?",
	"Find ML videos from last month",
	"Create a playlist of cooking videos",
	"How has my taste changed over time?",
	"Show me short tech tutorials",
];

export default function ChatPage() {
	const { isReady, isAuthenticated } = useAuthGuard();

	const [sessions, setSessions] = useState<ChatSession[]>([]);
	const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
	const [messages, setMessages] = useState<ChatMessage[]>([]);
	const [input, setInput] = useState("");
	const [loading, setLoading] = useState(false);
	const [loadingSessionMessages, setLoadingSessionMessages] = useState(false);
	const [activeTool, setActiveTool] = useState<string | null>(null);
	const messagesEndRef = useRef<HTMLDivElement>(null);

	const scrollToBottom = useCallback(() => {
		messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
	}, []);

	// biome-ignore lint/correctness/useExhaustiveDependencies: messages triggers scroll on new messages
	useEffect(() => {
		scrollToBottom();
	}, [messages, scrollToBottom]);

	const loadSessionMessages = useCallback(async (sessionId: string) => {
		setLoadingSessionMessages(true);
		try {
			const response = await chatApi.getSessionMessages(sessionId);
			const history: ChatMessage[] = response.data.map(
				(msg: {
					id: number;
					role: "user" | "assistant";
					content: string;
					tool_calls?: Array<{
						tool: string;
						arguments: Record<string, unknown>;
					}>;
					tool_results?: Array<{ tool: string; result: unknown }>;
					created_at: string;
				}) => ({
					id: msg.id,
					role: msg.role,
					content: msg.content,
					toolCalls: msg.tool_calls || [],
					toolResults: msg.tool_results || [],
					created_at: msg.created_at,
				}),
			);
			setMessages(history);
		} catch {
			setMessages([]);
		} finally {
			setLoadingSessionMessages(false);
		}
	}, []);

	const fetchSessions = useCallback(async () => {
		try {
			const response = await chatApi.getSessions();
			const fetchedSessions: ChatSession[] = response.data;
			setSessions(fetchedSessions);

			if (fetchedSessions.length === 0) {
				setActiveSessionId(null);
				setMessages([]);
				return;
			}

			const storedSessionId = localStorage.getItem("active_chat_session_id");
			const preferredSessionId =
				activeSessionId ||
				(storedSessionId &&
				fetchedSessions.some((s) => s.session_id === storedSessionId)
					? storedSessionId
					: fetchedSessions[0].session_id);

			if (!preferredSessionId) return;

			if (activeSessionId !== preferredSessionId) {
				setActiveSessionId(preferredSessionId);
				await loadSessionMessages(preferredSessionId);
			}
		} catch {
			// Failed to fetch sessions
		}
	}, [activeSessionId, loadSessionMessages]);

	useEffect(() => {
		if (!isReady || !isAuthenticated) return;
		fetchSessions();
	}, [isReady, isAuthenticated, fetchSessions]);

	useEffect(() => {
		if (activeSessionId) {
			localStorage.setItem("active_chat_session_id", activeSessionId);
		}
	}, [activeSessionId]);

	const createNewSession = useCallback(async () => {
		try {
			const response = await chatApi.newSession();
			const newId = response.data.session_id;
			setActiveSessionId(newId);
			setMessages([]);
			localStorage.setItem("active_chat_session_id", newId);
			await fetchSessions();
		} catch {
			// Failed to create session
		}
	}, [fetchSessions]);

	const openSession = useCallback(
		async (sessionId: string) => {
			if (sessionId === activeSessionId) return;
			setActiveSessionId(sessionId);
			setActiveTool(null);
			await loadSessionMessages(sessionId);
		},
		[activeSessionId, loadSessionMessages],
	);

	const deleteSession = useCallback(
		async (sessionId: string) => {
			try {
				await chatApi.deleteSession(sessionId);
				if (activeSessionId === sessionId) {
					setActiveSessionId(null);
					setMessages([]);
					localStorage.removeItem("active_chat_session_id");
				}
				await fetchSessions();
			} catch {
				// Failed to delete session
			}
		},
		[activeSessionId, fetchSessions],
	);

	const sendMessage = useCallback(
		async (text: string) => {
			if (!text.trim() || loading) return;

			let sessionId = activeSessionId;
			if (!sessionId) {
				try {
					const response = await chatApi.newSession();
					sessionId = response.data.session_id;
					setActiveSessionId(sessionId);
					localStorage.setItem("active_chat_session_id", sessionId);
				} catch {
					return;
				}
			}

			const userMessage: ChatMessage = { role: "user", content: text };
			setMessages((prev) => [...prev, userMessage]);
			setInput("");
			setLoading(true);
			setActiveTool(null);

			try {
				const token = localStorage.getItem("access_token");
				const response = await fetch(chatApi.getMessageEndpoint(), {
					method: "POST",
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${token}`,
					},
					body: JSON.stringify({
						session_id: sessionId,
						message: text,
					}),
				});

				if (!response.ok || !response.body) {
					throw new Error("Failed to get response");
				}

				const reader = response.body.getReader();
				const decoder = new TextDecoder();
				let assistantMessage: ChatMessage = {
					role: "assistant",
					content: "",
					toolCalls: [],
					toolResults: [],
				};

				let buffer = "";
				let done = false;

				while (!done) {
					const { value, done: streamDone } = await reader.read();
					done = streamDone;

					if (value) {
						buffer += decoder.decode(value, { stream: true });
						const lines = buffer.split("\n");
						buffer = lines.pop() || "";

						for (const line of lines) {
							const data = line.trim();
							if (!data) continue;

							try {
								const parsed = JSON.parse(data);

								if (parsed.type === "done") {
									done = true;
									break;
								}

								if (parsed.type === "tool_call") {
									setActiveTool(parsed.tool);
									assistantMessage = {
										...assistantMessage,
										toolCalls: [
											...(assistantMessage.toolCalls || []),
											{
												tool: parsed.tool,
												arguments: parsed.arguments,
											},
										],
									};
								} else if (parsed.type === "tool_result") {
									setActiveTool(null);
									assistantMessage = {
										...assistantMessage,
										toolResults: [
											...(assistantMessage.toolResults || []),
											{
												tool: parsed.tool,
												result: parsed.result,
											},
										],
									};
								} else if (parsed.type === "message") {
									assistantMessage = {
										...assistantMessage,
										content: parsed.content,
									};
								} else if (parsed.type === "error") {
									assistantMessage = {
										...assistantMessage,
										content: parsed.content || "An error occurred.",
									};
								}

								setMessages((prev) => {
									const updated = [...prev];
									const lastIdx = updated.length - 1;
									if (lastIdx >= 0 && updated[lastIdx].role === "assistant") {
										updated[lastIdx] = assistantMessage;
									} else {
										updated.push(assistantMessage);
									}
									return updated;
								});
							} catch {
								// Skip malformed JSON lines
							}
						}
					}
				}
			} catch {
				setMessages((prev) => [
					...prev,
					{
						role: "assistant",
						content: "Sorry, something went wrong. Please try again.",
					},
				]);
			} finally {
				setLoading(false);
				setActiveTool(null);
				fetchSessions();
			}
		},
		[activeSessionId, loading, fetchSessions],
	);

	const handleKeyDown = (e: React.KeyboardEvent) => {
		if (e.key === "Enter" && !e.shiftKey) {
			e.preventDefault();
			sendMessage(input);
		}
	};

	if (!isReady || !isAuthenticated) {
		return (
			<div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
				<Spinner size="lg" />
			</div>
		);
	}

	return (
		<div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex flex-col">
			<Navbar />
			<div className="flex flex-1 overflow-hidden max-w-7xl mx-auto w-full">
				{/* Sidebar */}
				<div className="w-64 border-r border-gray-200 dark:border-gray-700 flex flex-col p-4 gap-2 hidden md:flex">
					<Button
						color="primary"
						variant="flat"
						startContent={<AddIcon fontSize="small" />}
						onPress={createNewSession}
						className="mb-2"
					>
						New Chat
					</Button>
					<ScrollShadow className="flex-1">
						{sessions.map((session) => (
							<div
								key={session.session_id}
								className={`flex items-center justify-between p-2 rounded-lg cursor-pointer text-sm ${
									activeSessionId === session.session_id
										? "bg-primary/10 text-primary"
										: "hover:bg-gray-100 dark:hover:bg-gray-800"
								}`}
							>
								{/* biome-ignore lint/a11y/useSemanticElements: Using div for click handler */}
								<div
									role="button"
									tabIndex={0}
									className="flex-1 truncate"
									onClick={() => openSession(session.session_id)}
									onKeyDown={(e) => {
										if (e.key === "Enter" || e.key === " ") {
											openSession(session.session_id);
										}
									}}
								>
									{session.title || "Chat"} ({session.message_count} msgs)
								</div>
								<Button
									isIconOnly
									size="sm"
									variant="light"
									onPress={() => deleteSession(session.session_id)}
								>
									<DeleteIcon fontSize="small" />
								</Button>
							</div>
						))}
					</ScrollShadow>
				</div>

				{/* Chat area */}
				<div className="flex-1 flex flex-col">
					{/* Messages */}
					<ScrollShadow className="flex-1 overflow-y-auto p-4 space-y-4">
						{loadingSessionMessages && (
							<div className="flex justify-center py-8">
								<Spinner />
							</div>
						)}

						{messages.length === 0 && !loadingSessionMessages && (
							<div className="flex flex-col items-center justify-center h-full gap-6">
								<AutoAwesomeIcon
									className="text-primary"
									sx={{ fontSize: 48 }}
								/>
								<div className="text-center space-y-2">
									<h2 className="text-xl font-semibold">
										Video Library Assistant
									</h2>
									<p className="text-gray-500 text-sm max-w-md">
										Ask questions about your video library, search for videos,
										create playlists, or explore your viewing trends.
									</p>
								</div>
								<div className="flex flex-wrap gap-2 justify-center max-w-lg">
									{SUGGESTED_PROMPTS.map((prompt) => (
										<Chip
											key={prompt}
											variant="bordered"
											className="cursor-pointer hover:bg-primary/10"
											onClick={() => sendMessage(prompt)}
										>
											{prompt}
										</Chip>
									))}
								</div>
							</div>
						)}

						{messages.map((msg, index) => (
							<div
								key={`msg-${
									// biome-ignore lint/suspicious/noArrayIndexKey: Messages don't have stable IDs
									index
								}`}
								className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
							>
								<div
									className={`max-w-[80%] ${
										msg.role === "user"
											? "bg-primary text-white rounded-2xl rounded-br-md px-4 py-2"
											: "space-y-2"
									}`}
								>
									{msg.role === "assistant" &&
										msg.toolCalls &&
										msg.toolCalls.length > 0 && (
											<div className="flex flex-wrap gap-1 mb-2">
												{msg.toolCalls.map((tc, i) => (
													<Chip
														key={`tool-${
															// biome-ignore lint/suspicious/noArrayIndexKey: Tool calls don't have stable IDs
															i
														}`}
														size="sm"
														variant="flat"
														color="secondary"
														startContent={<BuildIcon sx={{ fontSize: 14 }} />}
													>
														{tc.tool}
													</Chip>
												))}
											</div>
										)}
									{msg.role === "assistant" ? (
										<Card className="shadow-sm">
											<CardBody className="p-4">
												<div className="prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap">
													{msg.content}
												</div>
											</CardBody>
										</Card>
									) : (
										<p className="text-sm">{msg.content}</p>
									)}
								</div>
							</div>
						))}

						{loading && (
							<div className="flex justify-start">
								<Card className="shadow-sm">
									<CardBody className="p-4 flex items-center gap-2">
										<Spinner size="sm" />
										<span className="text-sm text-gray-500">
											{activeTool ? `Using ${activeTool}...` : "Thinking..."}
										</span>
									</CardBody>
								</Card>
							</div>
						)}

						<div ref={messagesEndRef} />
					</ScrollShadow>

					{/* Input area */}
					<div className="border-t border-gray-200 dark:border-gray-700 p-4">
						<div className="flex gap-2 max-w-3xl mx-auto">
							<Input
								placeholder="Ask about your video library..."
								value={input}
								onValueChange={setInput}
								onKeyDown={handleKeyDown}
								variant="bordered"
								size="lg"
								className="flex-1"
								isDisabled={loading}
							/>
							<Button
								isIconOnly
								color="primary"
								size="lg"
								onPress={() => sendMessage(input)}
								isDisabled={!input.trim() || loading}
							>
								<SendIcon />
							</Button>
						</div>
					</div>
				</div>
			</div>
		</div>
	);
}
