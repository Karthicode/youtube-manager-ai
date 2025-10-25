"use client";

import {
	Accordion,
	AccordionItem,
	Button,
	Card,
	CardBody,
	CardHeader,
	Divider,
	Link,
	Textarea,
} from "@heroui/react";
import EmailIcon from "@mui/icons-material/Email";
import GitHubIcon from "@mui/icons-material/GitHub";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import { useAuthStore } from "@/store/auth";

export default function Help() {
	const router = useRouter();
	const { isAuthenticated } = useAuthStore();
	const [mounted, setMounted] = useState(false);
	const [feedback, setFeedback] = useState("");

	// Handle hydration
	useEffect(() => {
		setMounted(true);
	}, []);

	useEffect(() => {
		if (!mounted) return;

		if (!isAuthenticated) {
			router.push("/");
			return;
		}
	}, [mounted, isAuthenticated, router]);

	const handleSubmitFeedback = () => {
		// TODO: Implement feedback submission
		alert(
			"Thank you for your feedback! This feature will be implemented soon.",
		);
		setFeedback("");
	};

	if (!mounted || !isAuthenticated) {
		return null;
	}

	return (
		<div className="min-h-screen bg-gray-50 dark:bg-gray-900">
			<Navbar />
			<div className="container mx-auto px-4 py-8 max-w-5xl">
				<div className="space-y-6">
					{/* Header */}
					<div className="text-center">
						<HelpOutlineIcon className="text-6xl text-primary mb-4" />
						<h1 className="text-3xl font-bold">Help & Feedback</h1>
						<p className="text-gray-600 dark:text-gray-400 mt-2">
							Get help with YouTube Manager or share your feedback
						</p>
					</div>

					{/* Quick Links */}
					<div className="grid md:grid-cols-3 gap-4">
						<Card className="hover:shadow-lg transition-shadow cursor-pointer">
							<CardBody className="text-center p-6">
								<GitHubIcon className="text-4xl mb-2 mx-auto" />
								<h3 className="font-semibold mb-1">GitHub</h3>
								<p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
									Report issues or contribute
								</p>
								<Link
									href="https://github.com/yourusername/youtube-manager"
									target="_blank"
									className="text-primary text-sm"
								>
									Visit Repository
								</Link>
							</CardBody>
						</Card>

						<Card className="hover:shadow-lg transition-shadow cursor-pointer">
							<CardBody className="text-center p-6">
								<EmailIcon className="text-4xl mb-2 mx-auto" />
								<h3 className="font-semibold mb-1">Email Support</h3>
								<p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
									Get help via email
								</p>
								<Link
									href="mailto:support@yourdomain.com"
									className="text-primary text-sm"
								>
									support@yourdomain.com
								</Link>
							</CardBody>
						</Card>

						<Card className="hover:shadow-lg transition-shadow cursor-pointer">
							<CardBody className="text-center p-6">
								<HelpOutlineIcon className="text-4xl mb-2 mx-auto" />
								<h3 className="font-semibold mb-1">Documentation</h3>
								<p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
									Read the user guide
								</p>
								<Link href="#faq" className="text-primary text-sm">
									View FAQ Below
								</Link>
							</CardBody>
						</Card>
					</div>

					{/* Feedback Form */}
					<Card>
						<CardHeader>
							<h2 className="text-xl font-semibold">Send Feedback</h2>
						</CardHeader>
						<Divider />
						<CardBody className="space-y-4">
							<p className="text-gray-600 dark:text-gray-400">
								We'd love to hear your thoughts, suggestions, or bug reports!
							</p>
							<Textarea
								placeholder="Share your feedback here..."
								minRows={5}
								value={feedback}
								onValueChange={setFeedback}
							/>
							<Button
								color="primary"
								onPress={handleSubmitFeedback}
								isDisabled={!feedback.trim()}
							>
								Submit Feedback
							</Button>
						</CardBody>
					</Card>

					{/* FAQ Section */}
					<Card id="faq">
						<CardHeader>
							<h2 className="text-xl font-semibold">
								Frequently Asked Questions
							</h2>
						</CardHeader>
						<Divider />
						<CardBody>
							<Accordion variant="splitted">
								<AccordionItem
									key="1"
									title="How does AI categorization work?"
									aria-label="AI categorization"
								>
									<p className="text-gray-600 dark:text-gray-400">
										Our AI analyzes your video titles, descriptions, and
										metadata to automatically assign relevant categories and
										tags. It uses OpenAI's GPT model with structured outputs to
										ensure consistent and accurate categorization.
									</p>
								</AccordionItem>

								<AccordionItem
									key="2"
									title="How often should I sync my videos?"
									aria-label="Sync frequency"
								>
									<p className="text-gray-600 dark:text-gray-400">
										You can sync as often as you like! We recommend syncing
										weekly if you frequently like new videos. The batch sync
										feature can fetch all your liked videos at once, while the
										quick sync fetches recent additions.
									</p>
								</AccordionItem>

								<AccordionItem
									key="3"
									title="What's the difference between Fast and Background categorization?"
									aria-label="Categorization modes"
								>
									<p className="text-gray-600 dark:text-gray-400">
										<strong>Fast mode</strong> processes videos in parallel and
										waits for completion (recommended for &lt;100 videos).
										<strong> Background mode</strong> returns immediately and
										processes videos asynchronously - perfect for large batches
										(100+ videos). Check Vercel logs to monitor background
										progress.
									</p>
								</AccordionItem>

								<AccordionItem
									key="4"
									title="Is my YouTube data secure?"
									aria-label="Data security"
								>
									<p className="text-gray-600 dark:text-gray-400">
										Yes! We use OAuth 2.0 for secure authentication with
										YouTube. Your credentials are never stored - only access
										tokens which you can revoke anytime. All data is stored
										securely in our database and never shared with third
										parties.
									</p>
								</AccordionItem>

								<AccordionItem
									key="5"
									title="Can I edit AI-generated categories?"
									aria-label="Edit categories"
								>
									<p className="text-gray-600 dark:text-gray-400">
										Currently, categories are generated by AI from a predefined
										list. You can re-categorize individual videos anytime.
										Manual category editing and custom categories are planned
										for future releases!
									</p>
								</AccordionItem>

								<AccordionItem
									key="6"
									title="What happens if I disconnect my YouTube account?"
									aria-label="Disconnect account"
								>
									<p className="text-gray-600 dark:text-gray-400">
										Disconnecting will revoke access to your YouTube data. Your
										existing categorized videos will remain in the app, but you
										won't be able to sync new videos until you reconnect.
									</p>
								</AccordionItem>
							</Accordion>
						</CardBody>
					</Card>

					{/* Feature Requests */}
					<Card>
						<CardHeader>
							<h2 className="text-xl font-semibold">Feature Roadmap</h2>
						</CardHeader>
						<Divider />
						<CardBody>
							<div className="space-y-3">
								<p className="text-gray-600 dark:text-gray-400">
									Upcoming features we're working on:
								</p>
								<ul className="list-disc list-inside space-y-2 text-gray-700 dark:text-gray-300">
									<li>Custom categories and tags</li>
									<li>Export data to CSV/JSON</li>
									<li>Playlist recommendations based on categories</li>
									<li>Video notes and timestamps</li>
									<li>Advanced filtering and search</li>
									<li>Browser extension for quick saves</li>
								</ul>
								<p className="text-sm text-gray-600 dark:text-gray-400 mt-4">
									Have a feature suggestion? Send us feedback above!
								</p>
							</div>
						</CardBody>
					</Card>
				</div>
			</div>
		</div>
	);
}
