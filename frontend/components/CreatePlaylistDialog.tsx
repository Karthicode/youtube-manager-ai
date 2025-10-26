"use client";

import {
	Button,
	Input,
	Modal,
	ModalBody,
	ModalContent,
	ModalFooter,
	ModalHeader,
	Select,
	SelectItem,
	Textarea,
} from "@heroui/react";
import { useEffect, useState } from "react";

interface FilterParams {
	category_ids?: number[];
	tag_ids?: number[];
	search?: string;
	is_categorized?: boolean;
}

interface CreatePlaylistDialogProps {
	isOpen: boolean;
	onClose: () => void;
	onConfirm: (title: string, description: string, privacyStatus: string) => void;
	filterParams: FilterParams;
	videoCount: number;
	isCreating: boolean;
}

// Helper function to generate playlist title from filters
function generatePlaylistTitle(
	filterParams: FilterParams,
	categories: string[],
	tags: string[],
): string {
	const parts: string[] = [];

	if (categories.length > 0) {
		parts.push(categories.join(" + "));
	}

	if (tags.length > 0) {
		parts.push(tags.join(" + "));
	}

	if (filterParams.search) {
		parts.push(`"${filterParams.search}"`);
	}

	if (filterParams.is_categorized === true) {
		parts.push("Categorized");
	} else if (filterParams.is_categorized === false) {
		parts.push("Not Categorized");
	}

	return parts.length > 0 ? parts.join(" - ") : "My Playlist";
}

export default function CreatePlaylistDialog({
	isOpen,
	onClose,
	onConfirm,
	filterParams,
	videoCount,
	isCreating,
}: CreatePlaylistDialogProps) {
	// TODO: Fetch actual category/tag names from IDs
	const categoryNames: string[] = [];
	const tagNames: string[] = [];

	const [title, setTitle] = useState("");
	const [description, setDescription] = useState("");
	const [privacyStatus, setPrivacyStatus] = useState("private");

	// Generate default title from filters
	const defaultTitle = generatePlaylistTitle(
		filterParams,
		categoryNames,
		tagNames,
	);

	// Initialize title when dialog opens
	useEffect(() => {
		if (isOpen && !isCreating) {
			setTitle(defaultTitle);
			setDescription("");
			setPrivacyStatus("private");
		}
	}, [isOpen, defaultTitle, isCreating]);

	const handleConfirm = () => {
		if (title.trim()) {
			onConfirm(title, description, privacyStatus);
		}
	};

	const handleClose = () => {
		if (!isCreating) {
			onClose();
		}
	};

	return (
		<Modal
			isOpen={isOpen}
			onClose={handleClose}
			size="2xl"
			isDismissable={!isCreating}
			hideCloseButton={isCreating}
		>
			<ModalContent>
				{(onClose) => (
					<>
						<ModalHeader className="flex flex-col gap-1">
							Create YouTube Playlist
						</ModalHeader>
						<ModalBody>
							<div className="space-y-4">
								{/* Playlist Title */}
								<Input
									label="Playlist Title"
									placeholder="Enter playlist title"
									value={title}
									onValueChange={setTitle}
									variant="bordered"
									isRequired
									isDisabled={isCreating}
									description="Required - will be visible on YouTube"
								/>

								{/* Description */}
								<Textarea
									label="Description"
									placeholder="Optional description for your playlist"
									value={description}
									onValueChange={setDescription}
									variant="bordered"
									minRows={3}
									maxRows={5}
									isDisabled={isCreating}
									description="Optional - add context about this playlist"
								/>

								{/* Privacy Setting */}
								<Select
									label="Privacy"
									placeholder="Select privacy setting"
									selectedKeys={[privacyStatus]}
									onSelectionChange={(keys) => {
										const selected = Array.from(keys)[0];
										if (selected) setPrivacyStatus(selected as string);
									}}
									variant="bordered"
									isDisabled={isCreating}
									description="Who can view this playlist"
								>
									<SelectItem key="private">
										Private - Only you can view
									</SelectItem>
									<SelectItem key="unlisted">
										Unlisted - Anyone with link can view
									</SelectItem>
									<SelectItem key="public">
										Public - Anyone can find and view
									</SelectItem>
								</Select>

								{/* Video Count Info */}
								<div className="bg-blue-50 dark:bg-blue-950/30 p-4 rounded-lg border border-blue-200 dark:border-blue-800">
									<p className="text-sm text-blue-900 dark:text-blue-100">
										<strong>{videoCount}</strong> video
										{videoCount !== 1 ? "s" : ""} will be added to this
										playlist
									</p>
									{videoCount > 250 && (
										<p className="text-xs text-blue-700 dark:text-blue-300 mt-1">
											First 250 videos will be added immediately. Remaining{" "}
											{videoCount - 250} videos will be added in the background.
										</p>
									)}
								</div>
							</div>
						</ModalBody>
						<ModalFooter>
							<Button
								color="danger"
								variant="light"
								onPress={handleClose}
								isDisabled={isCreating}
							>
								Cancel
							</Button>
							<Button
								color="primary"
								onPress={handleConfirm}
								isLoading={isCreating}
								isDisabled={!title.trim() || isCreating}
							>
								{isCreating ? "Creating..." : "Create Playlist"}
							</Button>
						</ModalFooter>
					</>
				)}
			</ModalContent>
		</Modal>
	);
}
