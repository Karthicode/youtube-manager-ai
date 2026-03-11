# youtube-manager-ai Development Patterns

> Auto-generated skill from repository analysis

## Overview

This skill covers development patterns for the youtube-manager-ai project, a full-stack application with a Python backend and TypeScript/React frontend. The codebase follows conventional commit patterns and includes common workflows for UI theming, database migrations, React state management, video player components, backend configuration, and chat interface enhancements.

## Coding Conventions

### File Naming
- **Frontend**: Use camelCase for component files (e.g., `VideoCard.tsx`, `GlobalMiniPlayer.tsx`)
- **Backend**: Use snake_case for Python files (e.g., `agent_service.py`, `chat.py`)

### Import Style
```typescript
// Frontend - Use aliases for cleaner imports
import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
```

```python
# Backend - Standard Python import conventions
from sqlalchemy import Column, Integer, String
from app.models.base import Base
```

### Export Style
- Use default exports for main components
- Named exports for utilities and types

### Commit Conventions
- **Format**: `<type>: <description>` (avg 63 chars)
- **Types**: `feat`, `fix`, `refactor`, `chore`
- **Examples**: 
  - `feat: add video playlist management`
  - `fix: resolve light mode color visibility`

## Workflows

### Light Mode UI Fixes
**Trigger:** When components have hardcoded colors or poor light mode visibility  
**Command:** `/fix-light-mode`

1. **Identify hardcoded colors** in component styles
   ```tsx
   // Before: Hardcoded colors
   <div className="bg-gray-900 text-white">
   
   // After: Theme-aware classes
   <div className="bg-background text-foreground">
   ```

2. **Replace with theme-aware classes** using CSS variables or Tailwind's dark mode classes
3. **Test visibility in light mode** by switching theme in browser
4. **Update affected components** across the frontend:
   - `frontend/components/VideoCard.tsx`
   - `frontend/app/chat/page.tsx`
   - `frontend/components/Navbar.tsx`
   - `frontend/app/dashboard/page.tsx`
   - `frontend/app/insights/page.tsx`
   - `frontend/app/playlists/page.tsx`
   - `frontend/app/videos/page.tsx`

### Add Database Migration
**Trigger:** When adding new database schema changes  
**Command:** `/add-migration`

1. **Create Alembic migration file**
   ```bash
   cd backend
   alembic revision --autogenerate -m "Add new table/column"
   ```

2. **Update SQLAlchemy models**
   ```python
   # backend/app/models/new_model.py
   from sqlalchemy import Column, Integer, String
   from app.models.base import Base
   
   class NewModel(Base):
       __tablename__ = "new_table"
       id = Column(Integer, primary_key=True)
       name = Column(String(255))
   ```

3. **Add to models/__init__.py**
   ```python
   from .new_model import NewModel
   ```

4. **Update schemas if needed** in `backend/app/schemas/`
5. **Add router endpoints** in `backend/app/routers/`

### React Infinite Loop Fix
**Trigger:** When components have infinite re-fetch or re-render issues  
**Command:** `/fix-infinite-loop`

1. **Identify problematic state dependency** causing infinite loops
   ```tsx
   // Problematic: state in dependency array
   useEffect(() => {
     fetchData(someState)
   }, [someState, fetchData])
   ```

2. **Replace with useRef for non-reactive access**
   ```tsx
   const someStateRef = useRef(someState)
   someStateRef.current = someState
   ```

3. **Update useCallback dependencies**
   ```tsx
   const fetchData = useCallback(() => {
     // Use ref instead of state
     apiCall(someStateRef.current)
   }, []) // Remove state from deps
   ```

4. **Remove state from effect dependencies**

### Player Component Iteration
**Trigger:** When improving video playback functionality or fixing player issues  
**Command:** `/update-player`

1. **Update player component logic** in player components
2. **Modify store state management** in `frontend/store/miniPlayer.ts`
   ```typescript
   interface MiniPlayerState {
     isOpen: boolean
     videoId: string | null
     // Add new state properties
   }
   ```

3. **Update global styles if needed** in `frontend/app/globals.css`
4. **Test playback functionality** across different video sources

**Key Files:**
- `frontend/components/player/GlobalMiniPlayer.tsx`
- `frontend/components/player/VidstackYouTubeSurface.tsx`
- `frontend/components/player/YouTubePlayerSurface.tsx`

### Backend Config Adjustment
**Trigger:** When changing backend settings, database URLs, or feature flags  
**Command:** `/update-config`

1. **Identify config parameter** that needs adjustment
2. **Update backend/app/config.py**
   ```python
   import os
   from pydantic import BaseSettings
   
   class Settings(BaseSettings):
       database_url: str = os.getenv("DATABASE_URL")
       new_feature_flag: bool = os.getenv("NEW_FEATURE", False)
   ```

3. **Test configuration change** in development environment
4. **Update related services if needed** that depend on the config

### Chat Interface Enhancement
**Trigger:** When enhancing chat features or fixing chat-related bugs  
**Command:** `/enhance-chat`

1. **Update chat page component** with new functionality
   ```tsx
   // frontend/app/chat/page.tsx
   const [messages, setMessages] = useState([])
   const [isStreaming, setIsStreaming] = useState(false)
   ```

2. **Modify chat router if needed** in `backend/app/routers/chat.py`
3. **Update chat schemas/services** in related backend files
4. **Test chat functionality** including streaming and session management

## Testing Patterns

- **Test files**: Follow `*.test.*` pattern
- **Framework**: Testing framework not explicitly detected
- **Location**: Tests likely co-located with components or in dedicated test directories

## Commands

| Command | Purpose |
|---------|---------|
| `/fix-light-mode` | Fix color schemes and visibility issues for light mode theme |
| `/add-migration` | Add new database tables or columns with proper migration and model updates |
| `/fix-infinite-loop` | Fix useEffect/useCallback infinite re-render loops |
| `/update-player` | Refactor or enhance video player components |
| `/update-config` | Update backend configuration settings |
| `/enhance-chat` | Improve chat page functionality and fix streaming issues |