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
import { motion } from "framer-motion";
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
			<div className="min-h-screen bg-background flex items-center justify-center">
				<Spinner size="lg" color="primary" />
			</div>
		);
	}

	return (
		<div className="h-screen bg-background flex flex-col overflow-hidden">
			<Navbar />
			<div className="flex flex-1 overflow-hidden max-w-7xl mx-auto w-full">
				{/* Sidebar */}
				<div className="w-64 border-r border-border bg-surface flex-col p-4 gap-2 hidden md:flex">
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
								className={`flex items-center justify-between p-2 rounded-lg cursor-pointer text-sm transition-colors ${
									activeSessionId === session.session_id
										? "bg-[#E63946]/8 border-l-2 border-[#E63946] text-text-primary"
										: "hover:bg-surface-elevated text-text-secondary"
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
								<Spinner color="primary" />
							</div>
						)}

						{messages.length === 0 && !loadingSessionMessages && (
							<div className="flex flex-col items-center justify-center h-full gap-6 dot-grid rounded-xl py-16">
								<AutoAwesomeIcon
									className="text-[#E63946]"
									sx={{ fontSize: 48 }}
								/>
								<div className="text-center space-y-2">
									<h2 className="font-display text-xl font-semibold text-text-primary">
										Video Library Assistant
									</h2>
									<p className="text-text-secondary text-sm max-w-md">
										Ask questions about your video library, search for videos,
										create playlists, or explore your viewing trends.
									</p>
								</div>
								<div className="flex flex-wrap gap-2 justify-center max-w-lg">
									{SUGGESTED_PROMPTS.map((prompt) => (
										<button
											key={prompt}
											type="button"
											className="px-3 py-1.5 text-sm bg-surface-elevated border border-border hover:border-[#E63946] text-text-secondary hover:text-text-primary rounded-full transition-all cursor-pointer"
											onClick={() => sendMessage(prompt)}
										>
											{prompt}
										</button>
									))}
								</div>
							</div>
						)}

						{messages.map((msg, index) => (
							<motion.div
								key={`msg-${
									// biome-ignore lint/suspicious/noArrayIndexKey: Messages don't have stable IDs
									index
								}`}
								initial={{ opacity: 0, y: 8 }}
								animate={{ opacity: 1, y: 0 }}
								transition={{ duration: 0.25, ease: "easeOut" }}
								className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
							>
								<div
									className={`max-w-[80%] ${
										msg.role === "user"
											? "bg-[#E63946] text-white rounded-2xl rounded-br-sm px-4 py-2"
											: "space-y-3"
									}`}
								>
									{/* Tool Calls Section */}
									{msg.role === "assistant" &&
										msg.toolCalls &&
										msg.toolCalls.length > 0 && (
											<div className="flex items-center gap-1.5 flex-wrap px-1">
												<BuildIcon
													sx={{ fontSize: 13 }}
													className="text-[#06B6D4]"
												/>
												{msg.toolCalls.map((tc, i) => (
													<Chip
														// biome-ignore lint/suspicious/noArrayIndexKey: Tool calls don't have stable IDs
														key={i}
														size="sm"
														variant="flat"
														color="secondary"
														className="text-xs"
													>
														{tc.tool.replace(/_/g, " ")}
													</Chip>
												))}
											</div>
										)}

									{/* Assistant Message */}
									{msg.role === "assistant" ? (
										<Card className="border border-border shadow-none">
											<CardBody className="p-4">
												<div className="text-sm whitespace-pre-wrap text-text-primary leading-relaxed">
													{msg.content}
												</div>
											</CardBody>
										</Card>
									) : (
										<p className="text-sm">{msg.content}</p>
									)}
								</div>
							</motion.div>
						))}

						{loading && (
							<div className="flex justify-start">
								<div className="flex items-center gap-1.5 px-1 py-1 text-[#06B6D4]">
									{activeTool ? (
										<>
											<BuildIcon sx={{ fontSize: 13 }} />
											<Chip
												size="sm"
												variant="flat"
												color="secondary"
												className="text-xs"
											>
												{activeTool.replace(/_/g, " ")}
											</Chip>
											<Spinner size="sm" color="secondary" />
										</>
									) : (
										<>
											<Spinner size="sm" color="secondary" />
											<span className="text-sm text-text-secondary">
												Thinking...
											</span>
										</>
									)}
								</div>
							</div>
						)}

						<div ref={messagesEndRef} />
					</ScrollShadow>

					{/* Input area */}
					<div className="border-t border-border bg-surface p-4">
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
								classNames={{
									inputWrapper:
										"border-border hover:border-[#2A2A38] focus-within:!border-[#E63946]",
								}}
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
