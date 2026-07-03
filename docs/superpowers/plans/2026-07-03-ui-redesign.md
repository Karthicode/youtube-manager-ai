# UI Redesign (Dashboard, Playlists, Insights) + Auto-Sync Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the Dashboard, Playlists, and Insights pages into modular, clean layouts (per the approved spec at `docs/superpowers/specs/2026-07-03-ui-redesign-design.md`), then fix the "Last auto-sync failed" error.

**Architecture:** Pure frontend restructure for Tasks 1–5 (new `LibraryStatusStrip` and `RecentlyLiked` components; trimmed `DashboardStats`; cached-first Playlists; sectioned Insights with two components deleted). Tasks 6–8 fix the auto-sync failure: diagnose the stored Redis error, classify sync errors on the backend (`auth` vs `transient`), and surface a "Reconnect YouTube" action in the strip.

**Tech Stack:** Next.js 16 App Router, HeroUI, Tailwind (theme tokens), SWR, Zustand, MUI icons, date-fns. Backend: FastAPI, Redis, pytest.

## Global Constraints

- **Visual identity unchanged:** dark editorial theme, `#E63946` accent, `font-display` / `font-mono-editorial`, theme tokens `bg-surface`, `bg-surface-elevated`, `border-border`, `text-text-primary`, `text-text-secondary`.
- **Frontend quality gate after every change:** `cd frontend && npm run check:fix && npm run typecheck` — both must pass. There is NO frontend test framework; verification is typecheck + lint + visual check in the running app.
- **Backend quality gate after every change:** `cd backend && black . && ruff check . && mypy .` — all must pass.
- **Never `git push`.** Local commits only. Commit messages end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Frontend files use **tab indentation** (Biome). A PostToolUse hook auto-formats saved files.
- SWR global fetcher exists in `app/providers.tsx` (`api.get(url).then(r => r.data)`); string keys fetch automatically.

---

### Task 1: `LibraryStatusStrip` component (replaces AutoCategorizeBanner)

**Files:**
- Create: `frontend/components/LibraryStatusStrip.tsx`
- Modify: `frontend/app/dashboard/page.tsx` (swap banner for strip; remove header sync-time line)
- Delete: `frontend/components/AutoCategorizeBanner.tsx`

**Interfaces:**
- Consumes: `swrKeys.videoStats()`, `swrKeys.autoCategorizeStatus()`, `autoCategorizeApi.getStatus/retry` (`frontend/api/api.ts:307-332`), `CategorizationProgressSSE` (existing), `VideoStats` type.
- Produces: `<LibraryStatusStrip lastSyncAt={string | null} onJobComplete={() => void} />` — Task 8 later extends this same file with `error_type` handling.

- [ ] **Step 1: Create `frontend/components/LibraryStatusStrip.tsx`**

```tsx
"use client";

import { Button } from "@heroui/react";
import type { AxiosError } from "axios";
import { formatDistanceToNow } from "date-fns";
import { useState } from "react";
import useSWR, { mutate } from "swr";
import { autoCategorizeApi } from "@/api/api";
import { swrKeys } from "@/lib/swrKeys";
import type { VideoStats } from "@/types";
import CategorizationProgressSSE from "./CategorizationProgressSSE";

const STALE_THRESHOLD_HOURS = 36;

type StatusPayload = {
	status: string;
	reason?: string;
	stage?: string;
	error?: string;
	videos_synced?: number;
	videos_categorized?: number;
	job_id?: string;
	user_id?: number;
	timestamp?: string;
};

interface LibraryStatusStripProps {
	// User's last_sync_at from the auth store; drives the sync-recency segment
	// and staleness detection for users with no Redis status entry yet.
	lastSyncAt: string | null;
	// Called when a retry job completes so the parent can refresh video stats.
	onJobComplete?: () => void;
}

function fetchStatus(): Promise<StatusPayload> {
	return autoCategorizeApi.getStatus().then((r) => r.data);
}

function isStale(
	lastSyncAt: string | null,
	timestamp: string | undefined,
): boolean {
	const ref = timestamp ?? lastSyncAt;
	if (!ref) return true;
	const refMs = new Date(ref).getTime();
	if (Number.isNaN(refMs)) return true;
	const ageHours = (Date.now() - refMs) / (1000 * 60 * 60);
	return ageHours >= STALE_THRESHOLD_HOURS;
}

export default function LibraryStatusStrip({
	lastSyncAt,
	onJobComplete,
}: LibraryStatusStripProps) {
	const { data: status, error: statusError } = useSWR<StatusPayload>(
		swrKeys.autoCategorizeStatus(),
		fetchStatus,
		{ revalidateOnFocus: false, shouldRetryOnError: false },
	);
	const { data: stats } = useSWR<VideoStats>(swrKeys.videoStats());

	const [retrying, setRetrying] = useState(false);
	const [retryError, setRetryError] = useState<string | null>(null);
	const [jobId, setJobId] = useState<string | null>(null);

	const failed = !statusError && status?.status === "failed";
	const stale =
		!failed &&
		status?.status !== "triggered" &&
		isStale(lastSyncAt, status?.timestamp);
	const healthy = !failed && !stale;

	const dotColor = failed
		? "bg-[#E63946]"
		: stale
			? "bg-[#F59E0B]"
			: "bg-[#10b981]";

	const syncLabel = lastSyncAt
		? `Synced ${formatDistanceToNow(new Date(lastSyncAt), { addSuffix: true })}`
		: "Never synced";

	const problemMessage = failed
		? status?.stage === "sync"
			? "Last auto-sync failed — couldn't fetch your liked videos."
			: status?.stage === "trigger"
				? "Sync completed but categorization couldn't be queued."
				: "Last auto-sync failed."
		: "Auto-sync hasn't run in the last 36 hours.";

	const handleRetry = async () => {
		setRetrying(true);
		setRetryError(null);
		try {
			const response = await autoCategorizeApi.retry();
			if (response.data.status === "triggered" && response.data.job_id) {
				setJobId(response.data.job_id);
			} else {
				await mutate(swrKeys.autoCategorizeStatus());
			}
		} catch (err) {
			const axiosErr = err as AxiosError<{ detail?: { message?: string } }>;
			const detail = axiosErr.response?.data?.detail;
			setRetryError(
				typeof detail === "object" && detail?.message
					? detail.message
					: "Retry failed. Please try again.",
			);
		} finally {
			setRetrying(false);
		}
	};

	return (
		<div className="bg-surface border border-border rounded-xl px-4 py-2.5">
			<div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-text-secondary">
				{/* Sync recency */}
				<span className="flex items-center gap-2">
					<span className={`h-2 w-2 rounded-full ${dotColor}`} />
					<span>{syncLabel}</span>
				</span>

				{/* Categorization progress */}
				{stats && (
					<span className="flex items-center gap-2">
						<span className="w-24 h-1 bg-border rounded-full overflow-hidden">
							<span
								className="block h-full bg-[#E63946] rounded-full transition-all duration-700"
								style={{ width: `${stats.categorization_percentage}%` }}
							/>
						</span>
						<span className="font-mono-editorial text-text-primary">
							{stats.categorization_percentage.toFixed(1)}%
						</span>
						<span>categorized</span>
					</span>
				)}

				{/* Auto-sync problem + action (silent when healthy) */}
				{!healthy && !jobId && (
					<span className="flex items-center gap-3 sm:ml-auto">
						<span className={failed ? "text-[#E63946]" : "text-[#F59E0B]"}>
							{problemMessage}
						</span>
						<Button
							color="warning"
							size="sm"
							variant="flat"
							onPress={handleRetry}
							isLoading={retrying}
						>
							Retry now
						</Button>
					</span>
				)}
			</div>

			{retryError && (
				<p className="text-xs text-danger mt-2">{retryError}</p>
			)}

			{jobId && (
				<div className="mt-3">
					<CategorizationProgressSSE
						jobId={jobId}
						onComplete={() => {
							setJobId(null);
							mutate(swrKeys.autoCategorizeStatus());
							onJobComplete?.();
						}}
						onError={(err) => {
							setJobId(null);
							setRetryError(err || "Categorization failed.");
						}}
					/>
				</div>
			)}
		</div>
	);
}
```

Note: the strip renders even while `status` is loading — the sync-recency and
progress segments work off `lastSyncAt`/`stats` alone, and the problem segment
only appears once `status` resolves to failed/stale. This intentionally differs
from the old banner (which rendered nothing until status loaded) because the
strip always has content to show.

- [ ] **Step 2: Wire into `frontend/app/dashboard/page.tsx`**

Replace the import:

```tsx
// remove:
import AutoCategorizeBanner from "@/components/AutoCategorizeBanner";
// add:
import LibraryStatusStrip from "@/components/LibraryStatusStrip";
```

In the header block, delete the "Last synced" paragraph (it moves into the strip):

```tsx
// DELETE this block from the header:
{user?.last_sync_at && (
	<p className="text-xs text-text-secondary mt-1">
		Last synced{" "}
		{formatDistanceToNow(new Date(user.last_sync_at), {
			addSuffix: true,
		})}
	</p>
)}
```

Also remove the now-unused import `formatDistanceToNow` from `date-fns` in this file.

Replace the banner usage:

```tsx
// replace:
<AutoCategorizeBanner
	lastSyncAt={user?.last_sync_at ?? null}
	onJobComplete={refreshStats}
/>
// with:
<LibraryStatusStrip
	lastSyncAt={user?.last_sync_at ?? null}
	onJobComplete={refreshStats}
/>
```

- [ ] **Step 3: Delete `frontend/components/AutoCategorizeBanner.tsx`**

Run: `rm frontend/components/AutoCategorizeBanner.tsx`
Then confirm nothing else imports it: `grep -rn "AutoCategorizeBanner" frontend --include="*.tsx" --include="*.ts" -l` → expect no output.

- [ ] **Step 4: Quality gate**

Run: `cd frontend && npm run check:fix && npm run typecheck`
Expected: both exit 0, no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/LibraryStatusStrip.tsx frontend/app/dashboard/page.tsx
git rm frontend/components/AutoCategorizeBanner.tsx
git commit -m "feat: replace auto-categorize banner with library status strip

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Trim DashboardStats — remove Quick Actions + Progress card, inline Categorize

**Files:**
- Modify: `frontend/components/DashboardStats.tsx`
- Modify: `frontend/components/DashboardStatsSkeleton.tsx`

**Interfaces:**
- Consumes: existing props `{ batchCategorizing, onBatchCategorize, onCategoryClick }` (unchanged — `frontend/app/dashboard/page.tsx` needs no edits).
- Produces: same component signature; stats grid is now 3 cards; the Categorize dropdown lives inside the Uncategorized card.

- [ ] **Step 1: Edit `frontend/components/DashboardStats.tsx`**

1. Change the stats grid class from `grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4` to `grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4`.
2. **Delete the entire Progress card** (`{/* Progress */}` motion.div block, lines ~121-147).
3. **Delete the entire Quick Actions card** (`{/* Quick Actions */}` Card block, lines ~150-234) including the `Dropdown` there.
4. Replace the Uncategorized card body so the Categorize dropdown button renders inside it when `stats.uncategorized > 0`:

```tsx
{/* Uncategorized */}
<motion.div variants={itemVariants}>
	<Card className="bg-surface border border-border shadow-none h-full">
		<CardBody className="p-4 sm:p-5">
			<div className="flex justify-between items-start gap-2">
				<h3 className="text-[10px] sm:text-xs text-text-secondary uppercase tracking-widest mb-3">
					Uncategorized
				</h3>
				{stats.uncategorized > 0 && (
					<Dropdown>
						<DropdownTrigger>
							<Button
								color="warning"
								variant="flat"
								size="sm"
								isLoading={batchCategorizing}
							>
								Categorize
							</Button>
						</DropdownTrigger>
						<DropdownMenu aria-label="Categorization options">
							<DropdownItem
								key="fast"
								description="10 concurrent requests with real-time progress"
								onPress={() => onBatchCategorize(10)}
							>
								Fast (Recommended)
							</DropdownItem>
							<DropdownItem
								key="faster"
								description="20 concurrent requests (May hit rate limits)"
								onPress={() => onBatchCategorize(20)}
							>
								Faster
							</DropdownItem>
							<DropdownItem
								key="fastest"
								description="30 concurrent requests (Higher rate limit risk)"
								onPress={() => onBatchCategorize(30)}
							>
								Fastest
							</DropdownItem>
						</DropdownMenu>
					</Dropdown>
				)}
			</div>
			<p
				className={`font-mono-editorial text-3xl sm:text-4xl font-semibold whitespace-nowrap ${
					stats.uncategorized > 0 ? "text-[#F59E0B]" : "text-text-primary"
				}`}
			>
				{stats.uncategorized.toLocaleString()}
			</p>
			<p className="text-xs text-text-secondary mt-2">Needs tagging</p>
		</CardBody>
	</Card>
</motion.div>
```

5. Clean imports: `Dropdown, DropdownItem, DropdownMenu, DropdownTrigger, Button, Chip` stay (Chip used by Top Categories/Tags); remove `Link` only if no longer used — the Top Categories "View All" button still uses `Link`, so keep it.
6. Keep the Top Categories + Top Tags grid exactly as-is (it is the "library breakdown" band).

- [ ] **Step 2: Update `frontend/components/DashboardStatsSkeleton.tsx`**

Replace file contents:

```tsx
"use client";

import { Card, CardBody, CardHeader, Divider, Skeleton } from "@heroui/react";

export default function DashboardStatsSkeleton() {
	return (
		<>
			{/* Stats Overview skeleton — 3 cards */}
			<div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4">
				{Array.from({ length: 3 }).map((_, i) => (
					<Card
						// biome-ignore lint/suspicious/noArrayIndexKey: Static skeleton placeholders
						key={i}
						className="bg-surface border border-border shadow-none h-full"
					>
						<CardBody className="p-4 sm:p-5">
							<Skeleton className="h-3 w-20 rounded" />
							<Skeleton className="h-9 sm:h-10 w-24 rounded mt-3" />
							<Skeleton className="h-3 w-24 rounded mt-2" />
						</CardBody>
					</Card>
				))}
			</div>

			{/* Top Categories + Top Tags skeleton */}
			<div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
				<Card className="bg-surface border border-border shadow-none">
					<CardHeader className="pb-2 sm:pb-3 flex justify-between items-center">
						<Skeleton className="h-5 w-32 rounded" />
						<Skeleton className="h-8 w-16 rounded" />
					</CardHeader>
					<Divider className="bg-[#1E1E2A]" />
					<CardBody className="pt-3 sm:pt-4">
						<div className="space-y-2">
							{Array.from({ length: 5 }).map((_, i) => (
								// biome-ignore lint/suspicious/noArrayIndexKey: Static skeleton placeholders
								<div key={i}>
									<div className="flex justify-between items-center mb-1">
										<Skeleton className="h-4 w-24 rounded" />
										<Skeleton className="h-5 w-10 rounded" />
									</div>
									<Skeleton className="h-1 w-full rounded-full" />
								</div>
							))}
						</div>
					</CardBody>
				</Card>
				<Card className="bg-surface border border-border shadow-none">
					<CardHeader className="pb-2 sm:pb-3">
						<Skeleton className="h-5 w-24 rounded" />
					</CardHeader>
					<Divider className="bg-[#1E1E2A]" />
					<CardBody className="pt-3 sm:pt-4">
						<div className="flex flex-wrap gap-2">
							{Array.from({ length: 8 }).map((_, i) => (
								<Skeleton
									// biome-ignore lint/suspicious/noArrayIndexKey: Static skeleton placeholders
									key={i}
									className="h-6 w-20 rounded-md"
								/>
							))}
						</div>
					</CardBody>
				</Card>
			</div>
		</>
	);
}
```

- [ ] **Step 3: Quality gate**

Run: `cd frontend && npm run check:fix && npm run typecheck`
Expected: both exit 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/DashboardStats.tsx frontend/components/DashboardStatsSkeleton.tsx
git commit -m "feat: remove quick actions and progress card, inline categorize action

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: `RecentlyLiked` component

**Files:**
- Create: `frontend/components/RecentlyLiked.tsx`
- Modify: `frontend/app/dashboard/page.tsx` (render below `<ContinueWatching />`)

**Interfaces:**
- Consumes: `videosApi.getLikedVideos({ limit, sort_by, sort_order })` (`frontend/api/api.ts:104-113`, response shape `CursorPaginatedVideosResponse` — `{ videos: Video[] }`), `useMiniPlayerStore().openPlayer(video, queue, index, context)` (`frontend/store/miniPlayer.ts:44-50`), `Video` type.
- Produces: `<RecentlyLiked />` (no props). Renders `null` until loaded and when the list is empty (same pattern as `ContinueWatching`).

- [ ] **Step 1: Create `frontend/components/RecentlyLiked.tsx`**

```tsx
"use client";

import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { videosApi } from "@/api/api";
import { useMiniPlayerStore } from "@/store/miniPlayer";
import type { Video } from "@/types";

export default function RecentlyLiked() {
	const [videos, setVideos] = useState<Video[]>([]);
	const [loaded, setLoaded] = useState(false);
	const openPlayer = useMiniPlayerStore((s) => s.openPlayer);

	useEffect(() => {
		videosApi
			.getLikedVideos({ limit: 10, sort_by: "liked_at", sort_order: "desc" })
			.then((res) => setVideos(res.data.videos ?? []))
			.catch(() => {})
			.finally(() => setLoaded(true));
	}, []);

	if (!loaded || videos.length === 0) return null;

	const handlePlay = (index: number) => {
		const queue = videos.map((v) => ({
			id: v.id,
			youtubeId: v.youtube_id,
			title: v.title,
			channelTitle: v.channel_title,
			thumbnailUrl: v.thumbnail_url,
		}));
		openPlayer(queue[index], queue, index, {
			type: "videos",
			sourceTab: "liked",
		});
	};

	return (
		<section>
			<div className="flex items-center justify-between mb-3">
				<h2 className="text-lg font-semibold">Recently Liked</h2>
				<Link
					href="/videos"
					className="text-xs text-text-secondary hover:text-[#E63946] transition-colors"
				>
					View all →
				</Link>
			</div>
			<div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
				{videos.map((video, index) => (
					<button
						key={video.id}
						type="button"
						onClick={() => handlePlay(index)}
						className="group relative rounded-xl overflow-hidden border border-border bg-surface flex flex-col text-left"
					>
						{/* Thumbnail */}
						<div className="relative aspect-video bg-black">
							{video.thumbnail_url ? (
								<Image
									src={video.thumbnail_url}
									alt={video.title}
									fill
									className="object-cover"
									sizes="(max-width: 640px) 50vw, (max-width: 1024px) 25vw, 20vw"
								/>
							) : (
								<div className="w-full h-full bg-surface-elevated" />
							)}
							{/* Play overlay */}
							<div className="absolute inset-0 flex items-center justify-center bg-black/0 group-hover:bg-black/40 transition-colors">
								<PlayArrowIcon
									sx={{ fontSize: 32 }}
									className="text-white opacity-0 group-hover:opacity-100 transition-opacity"
								/>
							</div>
						</div>

						{/* Info */}
						<div className="p-2 flex-1 flex flex-col gap-1">
							<p className="text-xs font-semibold line-clamp-2 leading-tight text-text-primary">
								{video.title}
							</p>
							{video.channel_title && (
								<p className="text-[11px] text-text-secondary line-clamp-1">
									{video.channel_title}
								</p>
							)}
						</div>
					</button>
				))}
			</div>
		</section>
	);
}
```

- [ ] **Step 2: Wire into `frontend/app/dashboard/page.tsx`**

```tsx
import RecentlyLiked from "@/components/RecentlyLiked";
```

Render directly below `<ContinueWatching />`:

```tsx
{/* Continue Watching */}
<ContinueWatching />

{/* Recently Liked */}
<RecentlyLiked />
```

- [ ] **Step 3: Quality gate**

Run: `cd frontend && npm run check:fix && npm run typecheck`
Expected: both exit 0.

- [ ] **Step 4: Visual check**

Run: `cd frontend && npm run dev` (if not already running), open `http://localhost:3000/dashboard`.
Expected top-to-bottom order: greeting header (no sync line) → status strip → Continue Watching (if any) → Recently Liked grid → 3 stat cards → Top Categories/Top Tags. Clicking a Recently Liked card opens the mini player.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/RecentlyLiked.tsx frontend/app/dashboard/page.tsx
git commit -m "feat: add recently liked row to dashboard

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

**Note:** the dashboard band order in `app/dashboard/page.tsx` should end up as: header → `<LibraryStatusStrip>` → `<ContinueWatching />` → `<RecentlyLiked />` → SSE progress + sync modal (unchanged) → `<Suspense><DashboardStats /></Suspense>`.

---

### Task 4: Playlists page — cached-first with background sync + theme tokens

**Files:**
- Modify: `frontend/app/playlists/page.tsx`

**Interfaces:**
- Consumes: `playlistsApi.getPlaylists / syncPlaylists` (`frontend/api/api.ts:188-236`), `Playlist` type, existing `SmartPlaylistDialog`.
- Produces: no exported interface changes; page behavior changes only.

- [ ] **Step 1: Rewrite the data flow in `frontend/app/playlists/page.tsx`**

Replace the state + effects section (keep imports, add `Skeleton` to the HeroUI import):

```tsx
const [playlists, setPlaylists] = useState<Playlist[]>([]);
const [initialLoading, setInitialLoading] = useState(true);
const [syncing, setSyncing] = useState(false);
const [syncError, setSyncError] = useState(false);
const [smartDialogOpen, setSmartDialogOpen] = useState(false);

const fetchPlaylists = useCallback(async () => {
	try {
		const response = await playlistsApi.getPlaylists({ page_size: 50 });
		setPlaylists(response.data);
	} catch {
		// Failed to fetch playlists - UI will show empty state
	} finally {
		setInitialLoading(false);
	}
}, []);

const syncPlaylistsFromYouTube = useCallback(async () => {
	setSyncing(true);
	setSyncError(false);
	try {
		await playlistsApi.syncPlaylists({ max_results: 50 });
		await fetchPlaylists();
	} catch {
		setSyncError(true);
	} finally {
		setSyncing(false);
	}
}, [fetchPlaylists]);

useEffect(() => {
	if (!isReady || !isAuthenticated) return;
	// Cached-first: render stored playlists immediately, refresh from
	// YouTube in the background.
	fetchPlaylists();
	syncPlaylistsFromYouTube();
}, [isReady, isAuthenticated, fetchPlaylists, syncPlaylistsFromYouTube]);
```

- [ ] **Step 2: Rewrite the render section**

Header subtitle (background sync indicator instead of page takeover):

```tsx
<p className="mt-1 text-sm text-text-secondary">
	{playlists.length > 0
		? `${playlists.length} playlists`
		: initialLoading
			? "Loading…"
			: "No playlists found"}
	{syncing && <span className="ml-2 text-text-secondary">· Syncing…</span>}
	{!syncing && syncError && (
		<span className="ml-2 text-[#F59E0B]">
			· Sync failed — showing saved playlists
		</span>
	)}
</p>
```

Header buttons: keep both, replace hardcoded hexes on the Sync button with tokens:

```tsx
<Tooltip content="Sync from YouTube">
	<button
		type="button"
		onClick={syncPlaylistsFromYouTube}
		disabled={syncing}
		className="flex items-center gap-2 px-4 py-2 bg-surface text-text-primary font-medium rounded-xl hover:bg-surface-elevated transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed border border-border"
	>
		<SyncIcon
			sx={{ fontSize: 18 }}
			className={syncing ? "animate-spin" : ""}
		/>
		Sync
	</button>
</Tooltip>
```

(The AI Generate button keeps its `#E63946` accent — that is the brand accent.)

Content area — **delete the `syncing ? <full-page spinner> :` branch entirely**. New logic: skeleton grid only on true first load, otherwise the grid or empty state:

```tsx
{initialLoading && playlists.length === 0 ? (
	<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
		{Array.from({ length: 8 }).map((_, i) => (
			// biome-ignore lint/suspicious/noArrayIndexKey: Static skeleton placeholders
			<div key={i} className="rounded-xl border border-border overflow-hidden">
				<Skeleton className="aspect-video w-full" />
				<div className="p-3 space-y-2">
					<Skeleton className="h-4 w-3/4 rounded" />
					<Skeleton className="h-3 w-1/2 rounded" />
				</div>
			</div>
		))}
	</div>
) : playlists.length > 0 ? (
	/* existing motion.div grid — unchanged structure */
) : (
	/* existing empty state — unchanged structure */
)}
```

Playlist card class token swap (in the existing grid):
- `bg-[#0F0F14] border border-[#1E1E2A] ... hover:border-[#2A2A38]` → `bg-surface border border-border ... hover:border-surface-elevated`
- Title `text-[#F2F2F7]` → `text-text-primary`
- Synced-time `text-[#6B6B7E]` → `text-text-secondary`
- Empty state: `text-[#6B6B7E]` → `text-text-secondary`, `text-[#2A2A38]` → `text-text-secondary/60`
- Remove the `Spinner` import if no longer used anywhere in the file (the auth-guard early return still uses it — keep it there).

- [ ] **Step 3: Quality gate**

Run: `cd frontend && npm run check:fix && npm run typecheck`
Expected: both exit 0.

- [ ] **Step 4: Visual check**

Open `http://localhost:3000/playlists`. Expected: stored playlists render immediately, subtitle shows "· Syncing…" briefly, grid updates in place, no full-page spinner. Sync button still works manually.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/playlists/page.tsx
git commit -m "feat: cached-first playlists with background sync

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Insights restructure — remove Recommendations + TagCloud, thematic sections, compact summary

**Files:**
- Modify: `frontend/app/insights/page.tsx`
- Modify: `frontend/components/insights/InsightsSummaryCards.tsx`
- Modify: `frontend/components/insights/index.ts`
- Modify: `frontend/hooks/useInsights.ts` (remove `useInsightsRecommendations`)
- Modify: `frontend/lib/swrKeys.ts` (remove `insightsRecommendations`)
- Modify: `frontend/api/api.ts` (remove `insightsApi.getRecommendations`)
- Modify: `frontend/types/index.ts` (remove `ChannelRecommendation`, `RecommendationsResponse`)
- Delete: `frontend/components/insights/ChannelRecommendations.tsx`, `frontend/components/insights/TagCloud.tsx`
- Modify: `frontend/package.json` (uninstall `@visx/wordcloud` if only TagCloud uses it)

**Interfaces:**
- Consumes: existing `CategoryPieChart`, `ChannelBarChart`, `LikesTrendChart`, `DurationDistribution`, `TasteProfile` components and `useInsights*` hooks — all unchanged.
- Produces: `InsightsSummaryCards` keeps signature `{ data: InsightsOverview | null; loading?: boolean }` but renders a compact row.

- [ ] **Step 1: Rewrite `frontend/app/insights/page.tsx`**

```tsx
"use client";

import { Spinner } from "@heroui/react";
import {
	CategoryPieChart,
	ChannelBarChart,
	DurationDistribution,
	InsightsSummaryCards,
	LikesTrendChart,
	TasteProfile,
} from "@/components/insights";
import Navbar from "@/components/Navbar";
import { useAuthGuard } from "@/hooks";
import {
	useInsightsChannels,
	useInsightsContentDist,
	useInsightsDuration,
	useInsightsOverview,
	useInsightsTemporal,
} from "@/hooks/useInsights";

function SectionLabel({ children }: { children: React.ReactNode }) {
	return (
		<h2 className="text-[11px] uppercase tracking-widest text-text-secondary font-semibold">
			{children}
		</h2>
	);
}

export default function InsightsPage() {
	const { isReady, isAuthenticated } = useAuthGuard();

	const { data: overview, isLoading: loadingOverview } = useInsightsOverview();
	const {
		categories,
		isLoading: loadingContent,
		error: errContent,
	} = useInsightsContentDist();
	const {
		channels,
		isLoading: loadingChannels,
		error: errChannels,
	} = useInsightsChannels(10);
	const {
		temporal,
		isLoading: loadingTemporal,
		error: errTemporal,
	} = useInsightsTemporal();
	const {
		buckets,
		avgDuration,
		isLoading: loadingDuration,
		error: errDuration,
	} = useInsightsDuration();

	// Don't render anything until hydrated and authenticated
	if (!isReady || !isAuthenticated) {
		return (
			<div className="min-h-screen bg-background flex justify-center items-center">
				<Spinner size="lg" color="primary" />
			</div>
		);
	}

	return (
		<div className="min-h-screen bg-background">
			<Navbar />
			<div className="container mx-auto px-4 sm:px-6 py-6 sm:py-8 max-w-7xl">
				<div className="space-y-6">
					{/* Header */}
					<div>
						<h1 className="font-display text-2xl sm:text-3xl font-bold text-text-primary tracking-tight">
							Insights
						</h1>
						<p className="text-sm sm:text-base text-text-secondary mt-1">
							Discover patterns in your liked videos
						</p>
					</div>

					{/* Compact summary strip */}
					<InsightsSummaryCards data={overview} loading={loadingOverview} />

					{/* Taste Profile — marquee AI element */}
					<div className="space-y-3">
						<SectionLabel>Your taste profile</SectionLabel>
						<TasteProfile />
					</div>

					{/* What you watch / Who you watch */}
					<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
						<div className="space-y-3">
							<SectionLabel>What you watch</SectionLabel>
							<CategoryPieChart
								data={categories}
								totalVideos={overview?.total_videos}
								loading={loadingContent}
								error={errContent?.message ?? ""}
							/>
						</div>
						<div className="space-y-3">
							<SectionLabel>Who you watch</SectionLabel>
							<ChannelBarChart
								data={channels}
								loading={loadingChannels}
								error={errChannels?.message ?? ""}
							/>
						</div>
					</div>

					{/* How you watch */}
					<div className="space-y-3">
						<SectionLabel>How you watch</SectionLabel>
						<LikesTrendChart
							data={temporal}
							loading={loadingTemporal}
							error={errTemporal?.message ?? ""}
						/>
						<DurationDistribution
							data={buckets}
							avgDuration={avgDuration}
							loading={loadingDuration}
							error={errDuration?.message ?? ""}
						/>
					</div>
				</div>
			</div>
		</div>
	);
}
```

- [ ] **Step 2: Compact `frontend/components/InsightsSummaryCards.tsx`**

Replace file contents (same props, dense single row, theme tokens, no gradient icon boxes):

```tsx
"use client";

import type { InsightsOverview } from "@/types";

interface InsightsSummaryCardsProps {
	data: InsightsOverview | null;
	loading?: boolean;
}

function formatDuration(seconds: number): string {
	if (seconds < 60) return `${seconds}s`;
	if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
	const hours = Math.floor(seconds / 3600);
	const mins = Math.round((seconds % 3600) / 60);
	return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
}

function formatWatchTime(seconds: number): string {
	const hours = Math.floor(seconds / 3600);
	if (hours < 24) return `${hours} hours`;
	const days = Math.floor(hours / 24);
	const remainingHours = hours % 24;
	return remainingHours > 0 ? `${days}d ${remainingHours}h` : `${days} days`;
}

export default function InsightsSummaryCards({
	data,
	loading = false,
}: InsightsSummaryCardsProps) {
	const items = [
		{ label: "Videos", value: (data?.total_videos ?? 0).toLocaleString() },
		{ label: "Channels", value: (data?.unique_channels ?? 0).toLocaleString() },
		{
			label: "Categories",
			value: (data?.unique_categories ?? 0).toLocaleString(),
		},
		{ label: "Tags", value: (data?.unique_tags ?? 0).toLocaleString() },
		{
			label: "Avg Duration",
			value: formatDuration(data?.avg_video_duration_seconds ?? 0),
		},
		{
			label: "Watch Time",
			value: formatWatchTime(data?.total_watch_time_seconds ?? 0),
		},
	];

	return (
		<div className="grid grid-cols-3 lg:grid-cols-6 divide-x divide-border bg-surface border border-border rounded-xl overflow-hidden">
			{items.map((item) => (
				<div key={item.label} className="px-3 py-2.5 sm:px-4 sm:py-3">
					<p className="text-[10px] uppercase tracking-widest text-text-secondary">
						{item.label}
					</p>
					<p
						className={`font-mono-editorial text-lg sm:text-xl font-semibold text-text-primary mt-0.5 ${
							loading ? "animate-pulse" : ""
						}`}
					>
						{loading ? "…" : item.value}
					</p>
				</div>
			))}
		</div>
	);
}
```

(Note: `grid-cols-3` + `divide-x` puts a stray left border on rows 2 on small screens; acceptable, or the implementer may use `divide-y lg:divide-y-0` — visual check decides.)

- [ ] **Step 3: Delete dead code**

1. `rm frontend/components/insights/ChannelRecommendations.tsx frontend/components/insights/TagCloud.tsx`
2. `frontend/components/insights/index.ts` — remove the `ChannelRecommendations` and `TagCloud` export lines.
3. `frontend/hooks/useInsights.ts` — delete the whole `useInsightsRecommendations` function and the now-unused `ChannelRecommendation` import; delete `paramFetcher`'s usage check (it is still used by `useInsightsChannels`, so keep `paramFetcher`).
4. `frontend/lib/swrKeys.ts` — delete the `insightsRecommendations` key.
5. `frontend/api/api.ts` — delete `getRecommendations` from `insightsApi`.
6. `frontend/types/index.ts` — delete `ChannelRecommendation` and `RecommendationsResponse` interfaces. Also delete `TagCloudItem` **only if** `grep -rn "TagCloudItem" frontend --include="*.ts*" | grep -v types/index` returns nothing.
7. Check wordcloud usage: `grep -rln "@visx/wordcloud" frontend --include="*.tsx" --include="*.ts"` → if no output (TagCloud was the only consumer), run `cd frontend && npm uninstall @visx/wordcloud`.
8. Confirm no dangling references: `grep -rn "ChannelRecommendations\|useInsightsRecommendations\|TagCloud" frontend --include="*.tsx" --include="*.ts"` → expect no output (except possibly `getTagCloud` in `api.ts`/`tagsApi`, which belongs to the Videos-page tag features — leave `tagsApi.getTagCloud` alone if other pages use it; only the insights `TagCloud` component is in scope).

- [ ] **Step 4: Quality gate**

Run: `cd frontend && npm run check:fix && npm run typecheck`
Expected: both exit 0.

- [ ] **Step 5: Visual check**

Open `http://localhost:3000/insights`. Expected: compact summary strip → "Your taste profile" → "What you watch" (pie) beside "Who you watch" (channels) → "How you watch" (trend + duration). No Recommended Channels, no Tag Cloud.

- [ ] **Step 6: Commit**

```bash
git add -A frontend
git commit -m "feat: restructure insights into thematic sections

Removes Recommended Channels and Tag Cloud, promotes Taste Profile,
compacts summary cards into a dense strip.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Diagnose the auto-sync failure (investigation — no code until evidence)

**Files:**
- None modified. Output: a diagnosis note (paste findings into the session/PR notes).

**Interfaces:**
- Consumes: backend `GET /api/v1/cron/auto-categorize/status/me`, Redis key `auto_categorize:user_status:{user_id}` (`backend/app/services/auto_categorize_service.py:20`).
- Produces: the concrete stored `error` string + classification (auth / quota / transient) that Task 7's implementer references.

- [ ] **Step 1: Read the stored status**

Easiest path — browser devtools on the dashboard: Network tab, request to `/cron/auto-categorize/status/me`, read the JSON `error` field. Or from a shell (get a token from localStorage `access_token` in the browser):

```bash
curl -s http://localhost:8000/api/v1/cron/auto-categorize/status/me \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -m json.tool
```

Or read Redis directly (user id 1 assumed; adjust):

```bash
redis-cli get "auto_categorize:user_status:1"
```

Expected: JSON with `status: "failed"`, `stage: "sync"`, and an `error` string.

- [ ] **Step 2: Classify the error**

- `error` contains `"401"` / `"YouTube authentication expired"` / `"invalid_grant"` → **auth**: the refresh token is dead. `YouTubeService._build_credentials` already clears stored tokens and raises HTTPException 401 (`backend/app/services/youtube_service.py:82-95`). Fix = user reconnects YouTube (Task 8's Reconnect button; verify manually now by logging in again through the normal OAuth flow, then POST `/api/v1/auto-categorize/retry` and confirm `status` becomes `triggered` or `no_videos`).
- `error` contains `"quota"` / `"quotaExceeded"` → **quota**: verify in Google Cloud Console; the status clears on the next successful run. No code fix; document it.
- Anything else → **transient**: click Retry now on the dashboard strip (or POST `/api/v1/auto-categorize/retry`); confirm the status clears. Check backend logs (`api_logger` output) for the stack trace if it persists, and fix the specific root cause found — do not guess.

- [ ] **Step 3: Record the finding**

Write one paragraph: stored error, classification, action taken, result of the retry. Tasks 7–8 proceed regardless (they make failure states actionable for the future); if Step 2 already cleared the live error, note that the strip now shows healthy.

---

### Task 7: Backend — classify sync errors in the auto-categorize status

**Files:**
- Modify: `backend/app/services/auto_categorize_service.py`
- Test: `backend/tests/test_auto_categorize_service.py` (new)

**Interfaces:**
- Consumes: existing `run_for_user` sync-failure handler (`backend/app/services/auto_categorize_service.py:154-165`).
- Produces: `AutoCategorizeService.classify_sync_error(exc: Exception) -> str` returning `"auth"` or `"transient"`; the Redis status payload for `stage: "sync"` failures gains `"error_type"`. The status endpoint passes the payload through unchanged, so the frontend (Task 8) reads `error_type` with no router changes.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_auto_categorize_service.py`:

```python
"""Tests for auto-categorize sync error classification."""

from fastapi import HTTPException

from app.services.auto_categorize_service import AutoCategorizeService


def test_classify_sync_error_auth_for_401_http_exception() -> None:
    exc = HTTPException(
        status_code=401,
        detail="YouTube authentication expired. Please reconnect your account.",
    )
    assert AutoCategorizeService.classify_sync_error(exc) == "auth"


def test_classify_sync_error_transient_for_generic_exception() -> None:
    assert AutoCategorizeService.classify_sync_error(RuntimeError("boom")) == "transient"


def test_classify_sync_error_transient_for_non_401_http_exception() -> None:
    exc = HTTPException(status_code=500, detail="upstream error")
    assert AutoCategorizeService.classify_sync_error(exc) == "transient"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_auto_categorize_service.py -v`
Expected: FAIL — `AttributeError: ... has no attribute 'classify_sync_error'`.

- [ ] **Step 3: Implement**

In `backend/app/services/auto_categorize_service.py`:

Add import at the top:

```python
from fastapi import HTTPException
```

Add the static method to `AutoCategorizeService` (place it above `run_for_user`):

```python
@staticmethod
def classify_sync_error(exc: Exception) -> str:
    """Classify a sync-stage failure for the dashboard status strip.

    ``auth``: YouTube credentials are expired/revoked (YouTubeService raises
    HTTPException 401 in that case) — the user must reconnect their account.
    ``transient``: anything else — a retry may succeed.
    """
    if isinstance(exc, HTTPException) and exc.status_code == 401:
        return "auth"
    return "transient"
```

Update the sync-failure handler in `run_for_user` (the `except Exception as e:` block after `fetch_liked_videos`) to include the classification:

```python
        except Exception as e:
            api_logger.error(
                f"Failed to sync videos for user {user.id}: {e}", exc_info=True
            )
            result = {
                "status": "failed",
                "stage": "sync",
                "error": str(e),
                "error_type": AutoCategorizeService.classify_sync_error(e),
                "user_id": user.id,
            }
            AutoCategorizeService._write_user_status(user.id, result)
            return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_auto_categorize_service.py -v`
Expected: 3 passed.

- [ ] **Step 5: Quality gate**

Run: `cd backend && black . && ruff check . && mypy .`
Expected: all pass (black may reformat; rerun ruff/mypy after).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/auto_categorize_service.py backend/tests/test_auto_categorize_service.py
git commit -m "feat: classify auto-sync failures as auth vs transient

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: Frontend — actionable error + Reconnect YouTube in the status strip

**Files:**
- Modify: `frontend/api/api.ts` (add `error_type` to `autoCategorizeApi.getStatus` response type)
- Modify: `frontend/components/LibraryStatusStrip.tsx`

**Interfaces:**
- Consumes: `error_type?: string` from Task 7's status payload; `authApi.getLoginUrl()` (`frontend/api/api.ts:93`) returning `{ auth_url: string }` for the reconnect redirect.
- Produces: final `LibraryStatusStrip` behavior — auth failures show a **Reconnect YouTube** button; other failures show **Retry now** plus the stored error detail.

- [ ] **Step 1: Add `error_type` to the API type**

In `frontend/api/api.ts`, `autoCategorizeApi.getStatus`, add to the response generic after `error?: string;`:

```ts
			error_type?: string;
```

- [ ] **Step 2: Extend `LibraryStatusStrip.tsx`**

1. Add `error_type?: string;` to the `StatusPayload` type (after `error?: string;`).
2. Add `authApi` to the existing api import: `import { authApi, autoCategorizeApi } from "@/api/api";`
3. Below the `handleRetry` function, add:

```tsx
	const isAuthFailure = failed && status?.error_type === "auth";

	const handleReconnect = async () => {
		setRetrying(true);
		try {
			const response = await authApi.getLoginUrl();
			window.location.href = response.data.auth_url;
		} catch {
			setRetryError("Couldn't start YouTube reconnect. Please try again.");
			setRetrying(false);
		}
	};
```

4. Replace the problem segment (the `{!healthy && !jobId && (...)}` block) with:

```tsx
				{!healthy && !jobId && (
					<span className="flex items-center gap-3 sm:ml-auto">
						<span className={failed ? "text-[#E63946]" : "text-[#F59E0B]"}>
							{isAuthFailure
								? "YouTube connection expired."
								: problemMessage}
						</span>
						{isAuthFailure ? (
							<Button
								color="danger"
								size="sm"
								variant="flat"
								onPress={handleReconnect}
								isLoading={retrying}
							>
								Reconnect YouTube
							</Button>
						) : (
							<Button
								color="warning"
								size="sm"
								variant="flat"
								onPress={handleRetry}
								isLoading={retrying}
							>
								Retry now
							</Button>
						)}
					</span>
				)}
```

5. Below the `{retryError && ...}` line, surface the stored error detail for non-auth failures:

```tsx
			{failed && !isAuthFailure && status?.error && (
				<p className="text-xs text-text-secondary mt-1 line-clamp-1">
					{status.error}
				</p>
			)}
```

- [ ] **Step 3: Quality gate**

Run: `cd frontend && npm run check:fix && npm run typecheck`
Expected: both exit 0.

- [ ] **Step 4: Verify the failure states manually**

With backend + frontend running and a logged-in session:

1. Simulate an auth failure (adjust user id):
   `redis-cli set "auto_categorize:user_status:1" '{"status":"failed","stage":"sync","error":"401: YouTube authentication expired. Please reconnect your account.","error_type":"auth","user_id":1,"timestamp":"2026-07-03T00:00:00+00:00"}'`
   Reload dashboard → strip shows red dot, "YouTube connection expired.", **Reconnect YouTube** button.
2. Simulate a transient failure:
   `redis-cli set "auto_categorize:user_status:1" '{"status":"failed","stage":"sync","error":"HttpError 503 backend error","error_type":"transient","user_id":1,"timestamp":"2026-07-03T00:00:00+00:00"}'`
   Reload → red dot, failure message + stored error line, **Retry now** button; clicking it re-runs sync and the strip returns to healthy on success.
3. Restore the real status: click Retry now (a successful run overwrites the key), or `redis-cli del "auto_categorize:user_status:1"`.

- [ ] **Step 5: Commit**

```bash
git add frontend/api/api.ts frontend/components/LibraryStatusStrip.tsx
git commit -m "feat: reconnect action and error detail in library status strip

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: Final verification

**Files:** none (verification only).

- [ ] **Step 1: Full quality gates**

Run: `cd frontend && npm run check:fix && npm run typecheck && npm run build`
Expected: all pass, production build succeeds.
Run: `cd backend && black . && ruff check . && mypy . && pytest`
Expected: all pass.

- [ ] **Step 2: Walk all three pages in the running app**

- `/dashboard`: band order header → status strip → Continue Watching → Recently Liked → 3 stat cards (Categorize dropdown on Uncategorized) → Top Categories/Tags. No Quick Actions, no Progress card, no warning banner card. Sync All modal still works.
- `/playlists`: instant render, background sync indicator, manual Sync + AI Generate work.
- `/insights`: summary strip, Taste Profile on top, three labeled sections, no Recommended Channels / Tag Cloud.
- Status strip: healthy state (green dot) after Task 6/8 resolution.

- [ ] **Step 3: Report**

Summarize to the user: what changed per page, the auto-sync root cause found in Task 6, and how it was resolved. Do NOT push — ask the user about push/PR.
