"use client";

import {
	Button,
	Card,
	CardBody,
	CardHeader,
	Checkbox,
	CheckboxGroup,
	Chip,
	Divider,
	Input,
} from "@heroui/react";
import SearchIcon from "@mui/icons-material/Search";
import { useEffect, useState } from "react";
import { categoriesApi, tagsApi } from "@/api/api";
import type { Category, Tag } from "@/types";

interface FilterPanelProps {
	selectedCategories: number[];
	selectedTags: number[];
	searchQuery: string;
	showOnlyCategorized: boolean | null;
	onCategoriesChange: (categories: number[]) => void;
	onTagsChange: (tags: number[]) => void;
	onSearchChange: (search: string) => void;
	onCategorizationFilterChange: (value: boolean | null) => void;
	onClearFilters: () => void;
}

export default function FilterPanel({
	selectedCategories,
	selectedTags,
	searchQuery,
	showOnlyCategorized,
	onCategoriesChange,
	onTagsChange,
	onSearchChange,
	onCategorizationFilterChange,
	onClearFilters,
}: FilterPanelProps) {
	const [categories, setCategories] = useState<Category[]>([]);
	const [tags, setTags] = useState<Tag[]>([]);
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		const fetchFilters = async () => {
			try {
				const [categoriesRes, tagsRes] = await Promise.all([
					categoriesApi.getCategories(),
					tagsApi.getTags({ min_usage: 1, limit: 50 }),
				]);
				setCategories(categoriesRes.data);
				setTags(tagsRes.data);
			} catch (error) {
				console.error("Failed to fetch filters:", error);
			} finally {
				setLoading(false);
			}
		};

		fetchFilters();
	}, []);

	const hasActiveFilters =
		selectedCategories.length > 0 ||
		selectedTags.length > 0 ||
		searchQuery !== "" ||
		showOnlyCategorized !== null;

	return (
		<Card className="w-full shadow-md">
			<CardHeader className="flex justify-between items-center pb-3">
				<h3 className="text-lg font-semibold">Filters</h3>
				{hasActiveFilters && (
					<Button
						size="sm"
						color="danger"
						variant="light"
						onPress={onClearFilters}
						radius="md"
					>
						Clear All
					</Button>
				)}
			</CardHeader>
			<Divider />
			<CardBody className="gap-6 pt-4">
				{/* Search */}
				<div>
					<Input
						type="text"
						placeholder="Search videos..."
						value={searchQuery}
						onValueChange={onSearchChange}
						startContent={
							<SearchIcon fontSize="small" className="text-default-400" />
						}
						isClearable
						onClear={() => onSearchChange("")}
						variant="bordered"
						size="md"
						radius="lg"
					/>
				</div>

				<Divider />

				{/* Categorization Status */}
				<div className="space-y-3">
					<p className="text-sm font-semibold text-gray-700 dark:text-gray-300">
						Status
					</p>
					<div className="flex flex-wrap gap-2">
						<Chip
							color={showOnlyCategorized === null ? "primary" : "default"}
							variant={showOnlyCategorized === null ? "solid" : "bordered"}
							className="cursor-pointer hover:scale-105 transition-transform"
							onClick={() => onCategorizationFilterChange(null)}
							size="md"
							radius="md"
						>
							All
						</Chip>
						<Chip
							color={showOnlyCategorized === true ? "success" : "default"}
							variant={showOnlyCategorized === true ? "solid" : "bordered"}
							className="cursor-pointer hover:scale-105 transition-transform"
							onClick={() => onCategorizationFilterChange(true)}
							size="md"
							radius="md"
						>
							Categorized
						</Chip>
						<Chip
							color={showOnlyCategorized === false ? "warning" : "default"}
							variant={showOnlyCategorized === false ? "solid" : "bordered"}
							className="cursor-pointer hover:scale-105 transition-transform"
							onClick={() => onCategorizationFilterChange(false)}
							size="md"
							radius="md"
						>
							Not Categorized
						</Chip>
					</div>
				</div>

				<Divider />

				{/* Categories */}
				{!loading && categories.length > 0 && (
					<>
						<div className="space-y-3">
							<p className="text-sm font-semibold text-gray-700 dark:text-gray-300">
								Categories
							</p>
							<CheckboxGroup
								value={selectedCategories.map(String)}
								onValueChange={(values) =>
									onCategoriesChange(values.map(Number))
								}
								color="primary"
								size="md"
							>
								{categories.map((category) => (
									<Checkbox
										key={category.id}
										value={String(category.id)}
										classNames={{
											label: "text-sm",
										}}
									>
										{category.name}
									</Checkbox>
								))}
							</CheckboxGroup>
						</div>
						<Divider />
					</>
				)}

				{/* Tags */}
				{!loading && tags.length > 0 && (
					<div className="space-y-3">
						<p className="text-sm font-semibold text-gray-700 dark:text-gray-300">
							Tags
						</p>
						<div className="flex flex-wrap gap-2">
							{tags.map((tag) => (
								<Chip
									key={tag.id}
									color={selectedTags.includes(tag.id) ? "primary" : "default"}
									variant={selectedTags.includes(tag.id) ? "solid" : "bordered"}
									className="cursor-pointer hover:scale-105 transition-transform"
									onClick={() => {
										if (selectedTags.includes(tag.id)) {
											onTagsChange(selectedTags.filter((t) => t !== tag.id));
										} else {
											onTagsChange([...selectedTags, tag.id]);
										}
									}}
									size="sm"
									radius="md"
								>
									{tag.name} ({tag.usage_count})
								</Chip>
							))}
						</div>
					</div>
				)}
			</CardBody>
		</Card>
	);
}
