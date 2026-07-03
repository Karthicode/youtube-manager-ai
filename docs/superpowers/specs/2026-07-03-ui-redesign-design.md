# UI Redesign: Dashboard, Playlists, Insights + Auto-Sync Fix

**Date:** 2026-07-03
**Status:** Approved

## Goal

Restructure the Dashboard, Playlists, and Insights pages into a modular, clean,
functional layout. Group logically related elements, remove non-functional or
duplicate elements, and fix the "Last auto-sync failed" error afterward.

**Visual identity is unchanged:** dark editorial theme, `#E63946` accent,
existing fonts (`font-display`, `font-mono-editorial`) and theme tokens
(`bg-surface`, `border-border`, `text-text-primary`, `text-text-secondary`).
This is a layout/content restructure, not a restyle.

## 1. Dashboard (`app/dashboard/page.tsx`)

Structure, top to bottom:

### 1.1 Header
- Greeting + first name (unchanged).
- Single header action: **Sync All Videos** (existing behavior + modal, unchanged).
- The "Last synced X ago" line moves out of the header into the status strip.

### 1.2 Library status strip (new component: `LibraryStatusStrip`)
One slim row replacing the `AutoCategorizeBanner` card. Three segments:

- **Sync recency:** `● Synced 2h ago` — dot color: green (recent + healthy),
  amber (stale, >36h), red (last auto-sync failed).
- **Categorization progress:** `94.2% categorized` with a thin inline progress
  bar (replaces the removed Progress stat card).
- **Auto-sync health:** silent when healthy. On failure/staleness, the strip
  expands to show the message and the existing **Retry now** button, reusing
  the current retry + `CategorizationProgressSSE` logic from
  `AutoCategorizeBanner` (rehomed, not rewritten). Data sources unchanged:
  `swrKeys.autoCategorizeStatus()` + `user.last_sync_at`.

`AutoCategorizeBanner.tsx` is deleted once its logic moves into the strip.

### 1.3 Stats row (in `DashboardStats.tsx`)
Trimmed from 4 cards to 3:

- **Liked Videos** (unchanged)
- **Categorized** (unchanged)
- **Uncategorized** — gains a small **Categorize** button (visible when
  count > 0) with the existing Fast/Faster/Fastest concurrency dropdown.
  This is the rehomed functional item from Quick Actions. The existing
  SSE progress component still renders while a job runs.
- **Progress card deleted** — the % lives in the status strip.

### 1.4 Continue Watching
Unchanged.

### 1.5 Recently Liked (new component: `RecentlyLiked`)
- Horizontal thumbnail row of ~10 most recently liked videos.
- Uses the existing videos API: `sort_by=liked_at`, `sort_order=desc`,
  `page_size=10`. **No backend changes.**
- "View all →" link to `/videos`.
- Hidden when empty (same pattern as Continue Watching).

### 1.6 Library breakdown
Top Categories (clickable bars → `/videos?category=…`, unchanged behavior) +
Top Tags side by side. Restyled only to match module rhythm.

### Removed from Dashboard
- **Quick Actions card** (nav-link buttons duplicate the navbar; Categorize All
  moves to the Uncategorized card).
- **Progress stat card** (merged into status strip).
- **Standalone warning banner card** (merged into status strip).

## 2. Playlists (`app/playlists/page.tsx`)

### Behavior
- On load, fetch stored playlists from the DB and **render immediately** — no
  blocking full-page spinner.
- YouTube sync runs in the background on mount; header shows a quiet inline
  `↻ Syncing…` indicator (spinning icon on the existing Sync button). Grid
  refreshes in place when done.
- Sync failure: small inline message "Sync failed — showing saved playlists";
  the manual Sync button is the retry path.
- Skeleton grid only on true first load (no stored playlists yet).

### Layout/content
- Header unchanged: title, count subtitle, **Sync** + **AI Generate** buttons.
- Playlist cards keep their design; hardcoded hex colors (`#0F0F14`,
  `#1E1E2A`, `#2A2A38`, `#6B6B7E`, `#F2F2F7`) are replaced with theme tokens.
- Empty state content unchanged, restyled to tokens.
- Nothing removed on this page.

## 3. Insights (`app/insights/page.tsx`)

### Removed
- **Recommended Channels** (`ChannelRecommendations` component usage + its
  `useInsightsRecommendations` hook call; component file deleted).
- **Tag Cloud** (`TagCloud` usage removed; component file deleted).

### New structure
1. **Header + compact summary strip** — `InsightsSummaryCards` becomes one
   dense row (smaller numbers, tighter padding).
2. **Taste Profile** — promoted to the top, directly under the summary strip,
   as the marquee AI element.
3. **"What you watch"** — Category pie chart.
4. **"Who you watch"** — Channel bar chart.
5. **"How you watch"** — Likes trend (full width) + Duration distribution.

Each section gets a small uppercase editorial label header so the page reads
as organized chapters.

## 4. Auto-sync failure fix (after frontend work)

Symptom: dashboard shows "Last auto-sync failed. We couldn't fetch your latest
liked videos from YouTube." — backend wrote `status: failed, stage: sync` to
Redis, meaning `YouTubeService.fetch_liked_videos` threw during the cron run
(`AutoCategorizeService.run_for_user`). The real exception is in the Redis
payload `error` field, currently hidden by the frontend for sync-stage failures.

Plan (diagnosis-first):
1. **Diagnose:** read `/api/v1/auto-categorize/status` (or Redis key
   `auto_categorize:user_status:{user_id}`) for the stored `error`; check
   backend logs. Likely causes in order: expired/revoked YouTube OAuth refresh
   token, YouTube API quota exhaustion, transient API error persisted until
   the next run.
2. **Fix root cause:** e.g., dead refresh token → auth-error handling that
   directs the user to reconnect YouTube; transient error → retry logic or a
   successful re-run clears the status.
3. **Surface actionable detail in the status strip:** show stored error
   context; when the cause is auth, show a **Reconnect YouTube** action
   instead of a futile "Retry now".

## Error handling & testing

- Every new/changed component keeps loading (skeleton on first load), error
  (inline text), and empty states.
- Quality gates after every change:
  - Frontend: `npm run check:fix && npm run typecheck`
  - Backend (if touched): `black . && ruff check . && mypy .`
- Manual verification of all three pages in the running app at the end,
  including the status strip's failed/stale/healthy states.

## Out of scope

- Visual identity changes (fonts, colors, theme).
- Videos page, Chat page, Settings page.
- Backend API changes for the frontend restructure (Recently Liked uses the
  existing videos endpoint). Backend changes only as required by the
  auto-sync root-cause fix.
