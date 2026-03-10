# youtube-manager-ai Development Patterns

> Auto-generated skill from repository analysis

## Overview

This skill teaches development patterns for youtube-manager-ai, a Python-based YouTube management application with a React/TypeScript frontend and FastAPI backend. The codebase follows modern web development patterns with emphasis on responsive design, theme-aware UI components, video player functionality, and chat-based AI interactions. The application uses Redis for caching, Zustand for state management, and Tailwind CSS for styling.

## Coding Conventions

### File Naming
- Use camelCase for file names: `VideoCard.tsx`, `miniPlayer.ts`
- Frontend components in `frontend/components/`
- Backend routers in `backend/app/routers/`

### Import Style
```python
# Backend - Use alias imports
from app.redis_client import get_redis
from app.services.agent_service import AgentService

# Frontend - ES6 imports with aliases
import { useCallback, useEffect, useRef } from 'react'
import { VideoCard } from '@/components/VideoCard'
```

### Commit Conventions
- Use conventional commit format: `feat:`, `fix:`, `refactor:`, `chore:`
- Keep messages around 63 characters
- Examples: `feat: add mini player controls`, `fix: resolve infinite loop in playlists`

## Workflows

### Mobile Responsive Fixes
**Trigger:** When mobile UI needs adjustments or responsive breakpoints need fixing
**Command:** `/mobile-fix`

1. Identify mobile viewport issues by testing on small screens
2. Update component styling with Tailwind responsive utilities (`sm:`, `md:`, `lg:`)
3. Focus on common problem areas: FilterPanel, Navbar, page layouts
4. Test mobile layout across different breakpoints
5. Apply responsive classes for proper mobile experience

**Example:**
```tsx
// Before
<div className="flex w-full">

// After  
<div className="flex flex-col md:flex-row w-full">
```

### Light Mode Color Fixes
**Trigger:** When components are not visible or properly styled in light mode
**Command:** `/fix-light-mode`

1. Identify hardcoded dark colors that break in light mode
2. Replace with theme-aware Tailwind classes using dark: prefix
3. Update text colors, backgrounds, and borders systematically
4. Test components in both light and dark modes
5. Focus on VideoCard, page components, and Navbar

**Example:**
```tsx
// Before
<div className="bg-gray-800 text-white">

// After
<div className="bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white">
```

### Infinite Loop Bug Fixes
**Trigger:** When components are stuck in infinite re-fetch or re-render loops
**Command:** `/fix-infinite-loop`

1. Identify problematic useEffect or useCallback dependencies
2. Replace state variables with useRef for non-reactive references
3. Update dependency arrays to prevent unnecessary re-renders
4. Test that loops are eliminated and data still loads correctly
5. Common in playlist pages and chat components

**Example:**
```tsx
// Before
const [playlistId, setPlaylistId] = useState(id)
useEffect(() => {
  fetchPlaylist(playlistId)
}, [playlistId, fetchPlaylist])

// After  
const playlistIdRef = useRef(id)
useEffect(() => {
  fetchPlaylist(playlistIdRef.current)
}, [id]) // Stable dependency
```

### Mini Player Development
**Trigger:** When adding or modifying video playback features
**Command:** `/enhance-player`

1. Update GlobalMiniPlayer component with new functionality
2. Modify miniPlayer store (Zustand) for state management
3. Integrate changes with VideoCard components
4. Update VidstackYouTubeSurface for video surface handling
5. Add playback controls and progress tracking

**Example:**
```tsx
// Store update
interface MiniPlayerState {
  currentVideo: Video | null
  isPlaying: boolean
  setCurrentVideo: (video: Video) => void
  togglePlay: () => void
}
```

### Redis Client Fixes
**Trigger:** When Redis operations fail due to client initialization problems
**Command:** `/fix-redis`

1. Identify Redis connection failures in backend logs
2. Replace module-level redis imports with `get_redis()` function calls
3. Update affected routers (especially cron.py)
4. Ensure proper Redis client lifecycle management
5. Test Redis operations after changes

**Example:**
```python
# Before
from app.redis_client import redis_client
redis_client.set(key, value)

# After
from app.redis_client import get_redis
redis_client = get_redis()
redis_client.set(key, value)
```

### Chat System Development
**Trigger:** When developing chat features or fixing chat-related issues
**Command:** `/enhance-chat`

1. Update chat page component for UI improvements
2. Modify chat router endpoints for new functionality
3. Enhance agent service for better AI responses
4. Update chat schemas for proper data validation
5. Test streaming responses and session management

**Example:**
```python
# Chat router pattern
@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    message: ChatMessage,
    current_user: User = Depends(get_current_user)
):
    return await agent_service.process_message(session_id, message)
```

## Testing Patterns

- Test files follow `*.test.*` pattern
- Framework details not specified in repository
- Focus on testing responsive behavior, theme switching, and state management
- Manual testing required for video playback and chat streaming

## Commands

| Command | Purpose |
|---------|---------|
| `/mobile-fix` | Fix UI components for mobile viewport and responsive design |
| `/fix-light-mode` | Fix color schemes and visibility issues for light mode theme |
| `/fix-infinite-loop` | Fix infinite re-render loops caused by useCallback/useEffect dependencies |
| `/enhance-player` | Build and enhance video player functionality with state management |
| `/fix-redis` | Fix Redis client initialization and connection issues in backend |
| `/enhance-chat` | Build and enhance chat functionality with sessions and streaming |