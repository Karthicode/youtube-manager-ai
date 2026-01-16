"use client";

import {
	Button,
	Chip,
	Modal,
	ModalBody,
	ModalContent,
	ModalFooter,
	ModalHeader,
} from "@heroui/react";
import WarningIcon from "@mui/icons-material/Warning";

interface DeleteVideosDialogProps {
	isOpen: boolean;
	onClose: () => void;
	onConfirm: () => void;
	videoCount: number;
	tagNames: string[];
	isDeleting: boolean;
}

export default function DeleteVideosDialog({
	isOpen,
	onClose,
	onConfirm,
	videoCount,
	tagNames,
	isDeleting,
}: DeleteVideosDialogProps) {
	const handleClose = () => {
		if (!isDeleting) {
			onClose();
		}
	};

	return (
		<Modal
			isOpen={isOpen}
			onClose={handleClose}
			size="lg"
			isDismissable={!isDeleting}
			hideCloseButton={isDeleting}
		>
			<ModalContent>
				{(_onClose) => (
					<>
						<ModalHeader className="flex gap-2 items-center text-danger">
							<WarningIcon />
							Confirm Bulk Delete
						</ModalHeader>
						<ModalBody>
							<div className="space-y-4">
								<div className="bg-danger-50 dark:bg-danger-950/30 p-4 rounded-lg border border-danger-200 dark:border-danger-800">
									<p className="text-danger-700 dark:text-danger-300 font-medium">
										This action cannot be undone!
									</p>
									<p className="text-sm text-danger-600 dark:text-danger-400 mt-2">
										You are about to permanently delete{" "}
										<strong>{videoCount}</strong> video
										{videoCount !== 1 ? "s" : ""} from both YouTube (unlike) and
										your local database.
									</p>
								</div>

								<div>
									<p className="text-sm font-medium mb-2">
										Videos matching tags:
									</p>
									<div className="flex flex-wrap gap-2">
										{tagNames.map((name) => (
											<Chip key={name} color="primary" variant="flat" size="sm">
												{name}
											</Chip>
										))}
									</div>
								</div>

								<div className="text-sm text-gray-600 dark:text-gray-400">
									<p className="font-medium mb-1">What will happen:</p>
									<ul className="list-disc list-inside space-y-1">
										<li>Videos will be unliked on YouTube</li>
										<li>
											Videos will be removed from your liked videos playlist
										</li>
										<li>
											Videos will be permanently deleted from this application
										</li>
										<li>This does NOT delete the videos from YouTube itself</li>
									</ul>
								</div>

								{videoCount > 100 && (
									<div className="bg-warning-50 dark:bg-warning-950/30 p-3 rounded-lg border border-warning-200 dark:border-warning-800">
										<p className="text-sm text-warning-700 dark:text-warning-300">
											<strong>Note:</strong> Deleting {videoCount} videos may
											take several minutes and consume significant YouTube API
											quota.
										</p>
									</div>
								)}
							</div>
						</ModalBody>
						<ModalFooter>
							<Button
								variant="light"
								onPress={handleClose}
								isDisabled={isDeleting}
							>
								Cancel
							</Button>
							<Button
								color="danger"
								onPress={onConfirm}
								isLoading={isDeleting}
								isDisabled={isDeleting}
							>
								{isDeleting ? "Starting..." : `Delete ${videoCount} Videos`}
							</Button>
						</ModalFooter>
					</>
				)}
			</ModalContent>
		</Modal>
	);
}
