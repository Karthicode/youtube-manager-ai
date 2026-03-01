"use client";

import {
	Button,
	Card,
	CardBody,
	Chip,
	Input,
	Modal,
	ModalBody,
	ModalContent,
	ModalFooter,
	ModalHeader,
	Slider,
	Textarea,
} from "@heroui/react";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import PlaylistAddIcon from "@mui/icons-material/PlaylistAdd";
import TuneIcon from "@mui/icons-material/Tune";
import { useCallback, useState } from "react";
import { playlistsApi } from "@/api/api";
import type { PlaylistSuggestion, Video } from "@/types";

interface SmartPlaylistDialogProps {
	isOpen: boolean;
	onClose: () => void;
	onPlaylistCreated: () => void;
	videosMap?: Map<number, Video>;
}

export default function SmartPlaylistDialog({
	isOpen,
	onClose,
	onPlaylistCreated,
	videosMap,
}: SmartPlaylistDialogProps) {
	const [description, setDescription] = useState("");
	const [maxVideos, setMaxVideos] = useState(25);
	const [loading, setLoading] = useState(false);
	const [confirming, setConfirming] = useState(false);
	const [suggestion, setSuggestion] = useState<PlaylistSuggestion | null>(null);
	const [refinement, setRefinement] = useState("");
	const [error, setError] = useState<string | null>(null);
	const [created, setCreated] = useState(false);

	const handleGenerate = useCallback(
		async (refine?: boolean) => {
			if (!description.trim()) return;
			setLoading(true);
			setError(null);

			try {
				const response = await playlistsApi.generateSmartPlaylist({
					description: description.trim(),
					max_videos: maxVideos,
					refinement: refine ? refinement.trim() : undefined,
					previous_suggestion_id: refine
						? suggestion?.suggestion_id
						: undefined,
				});
				setSuggestion(response.data);
				setRefinement("");
			} catch {
				setError("Failed to generate playlist. Please try again.");
			} finally {
				setLoading(false);
			}
		},
		[description, maxVideos, refinement, suggestion?.suggestion_id],
	);

	const handleReset = useCallback(() => {
		setDescription("");
		setMaxVideos(25);
		setSuggestion(null);
		setRefinement("");
		setError(null);
		setCreated(false);
	}, []);

	const handleConfirm = useCallback(async () => {
		if (!suggestion) return;
		setConfirming(true);
		setError(null);

		try {
			await playlistsApi.confirmSmartPlaylist({
				suggestion_id: suggestion.suggestion_id,
				privacy_status: "private",
			});
			setCreated(true);
			setTimeout(() => {
				onPlaylistCreated();
				handleReset();
				onClose();
			}, 1500);
		} catch {
			setError("Failed to create playlist on YouTube. Please try again.");
		} finally {
			setConfirming(false);
		}
	}, [suggestion, onPlaylistCreated, onClose, handleReset]);

	const handleClose = () => {
		handleReset();
		onClose();
	};

	return (
		<Modal
			isOpen={isOpen}
			onClose={handleClose}
			size="3xl"
			scrollBehavior="inside"
		>
			<ModalContent>
				<ModalHeader className="flex items-center gap-2">
					<AutoAwesomeIcon className="text-primary" />
					<span>AI Smart Playlist</span>
				</ModalHeader>

				<ModalBody>
					{created ? (
						<div className="flex flex-col items-center justify-center py-12 gap-4">
							<CheckCircleIcon className="text-success" sx={{ fontSize: 64 }} />
							<p className="text-xl font-semibold">Playlist Created!</p>
							<p className="text-gray-500">
								Your playlist has been created on YouTube.
							</p>
						</div>
					) : !suggestion ? (
						<div className="space-y-6">
							<div>
								<Textarea
									label="Describe your playlist"
									placeholder='e.g., "Relaxing evening videos", "System design interview prep", "Quick tech news under 10 minutes"'
									value={description}
									onValueChange={setDescription}
									minRows={3}
									maxRows={5}
									variant="bordered"
								/>
							</div>

							<div className="space-y-2">
								<p className="text-sm font-medium">Max videos: {maxVideos}</p>
								<Slider
									aria-label="Max videos"
									step={5}
									minValue={5}
									maxValue={50}
									value={maxVideos}
									onChange={(val) =>
										setMaxVideos(typeof val === "number" ? val : val[0])
									}
									className="max-w-md"
									color="primary"
								/>
							</div>

							{error && <p className="text-danger text-sm">{error}</p>}
						</div>
					) : (
						<div className="space-y-6">
							{/* Suggestion header */}
							<div className="space-y-2">
								<h3 className="text-xl font-bold">{suggestion.title}</h3>
								<p className="text-gray-600 dark:text-gray-400">
									{suggestion.description}
								</p>
								<Chip color="primary" variant="flat" size="sm">
									{suggestion.theme_summary}
								</Chip>
							</div>

							{/* Video list with reasons */}
							<div className="space-y-3">
								<h4 className="font-semibold text-sm text-gray-500">
									{suggestion.videos.length} Videos Selected
								</h4>
								{suggestion.videos
									.sort((a, b) => a.order_position - b.order_position)
									.map((item, index) => {
										const video = videosMap?.get(item.video_id);
										return (
											<Card key={item.video_id} className="shadow-sm">
												<CardBody className="p-3">
													<div className="flex items-start gap-3">
														<div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-primary text-sm font-bold">
															{index + 1}
														</div>
														<div className="flex-1 min-w-0">
															<p className="font-medium text-sm truncate">
																{video?.title || `Video #${item.video_id}`}
															</p>
															{video?.channel_title && (
																<p className="text-xs text-gray-500">
																	{video.channel_title}
																</p>
															)}
															<p className="text-xs text-primary mt-1">
																{item.reason}
															</p>
														</div>
														{video?.thumbnail_url && (
															<img
																src={video.thumbnail_url}
																alt=""
																className="w-20 h-12 object-cover rounded flex-shrink-0"
															/>
														)}
													</div>
												</CardBody>
											</Card>
										);
									})}
							</div>

							{/* Watch order rationale */}
							<div className="bg-default-100 rounded-lg p-4">
								<h4 className="font-semibold text-sm mb-1">
									Watch Order Rationale
								</h4>
								<p className="text-sm text-gray-600 dark:text-gray-400">
									{suggestion.watching_order_rationale}
								</p>
							</div>

							{/* Refinement input */}
							<div className="space-y-2">
								<Input
									label="Refine suggestion"
									placeholder='e.g., "Remove gaming videos", "Add more short ones"'
									value={refinement}
									onValueChange={setRefinement}
									variant="bordered"
									startContent={
										<TuneIcon fontSize="small" className="text-gray-400" />
									}
								/>
								<Button
									size="sm"
									variant="flat"
									color="primary"
									isDisabled={!refinement.trim() || loading}
									isLoading={loading}
									onPress={() => handleGenerate(true)}
								>
									Refine
								</Button>
							</div>

							{error && <p className="text-danger text-sm">{error}</p>}
						</div>
					)}
				</ModalBody>

				<ModalFooter>
					{!suggestion && !created && (
						<>
							<Button variant="light" onPress={handleClose}>
								Cancel
							</Button>
							<Button
								color="primary"
								onPress={() => handleGenerate()}
								isDisabled={!description.trim() || loading}
								isLoading={loading}
								startContent={!loading && <AutoAwesomeIcon fontSize="small" />}
							>
								{loading ? "Generating..." : "Generate Playlist"}
							</Button>
						</>
					)}
					{suggestion && !created && (
						<>
							<Button variant="light" onPress={handleReset}>
								Start Over
							</Button>
							<Button
								color="primary"
								onPress={handleConfirm}
								isDisabled={confirming}
								isLoading={confirming}
								startContent={
									!confirming && <PlaylistAddIcon fontSize="small" />
								}
							>
								{confirming ? "Creating..." : "Confirm & Create"}
							</Button>
						</>
					)}
				</ModalFooter>
			</ModalContent>
		</Modal>
	);
}
