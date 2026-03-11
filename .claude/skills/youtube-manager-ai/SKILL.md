# youtube-manager-ai Development Patterns

> Auto-generated skill from repository analysis

## Overview

This skill teaches development patterns for the youtube-manager-ai project, a Python-based application with a React frontend for managing YouTube content. The codebase follows modern full-stack patterns with FastAPI backend, React frontend, Redis caching, PostgreSQL with Alembic migrations, and comprehensive error handling patterns.

## Coding Conventions

### File Naming
- Backend: snake_case for Python modules
- Frontend: camelCase for components and pages
- Test files: `*.test.*` pattern

### Import Patterns
```python
# Backend - Use aliases for common imports
from app.utils.logger import api_logger
from app.database.connection import get_redis
from app.models import VideoModel, PlaylistModel

# Frontend - Standard React imports
import { useState, useEffect, useCallback, useRef } from 'react'
```

### Commit Style
- Use conventional commits: `feat:`, `fix:`, `refactor:`, `chore:`
- Keep messages around 63 characters
- Examples: `feat: add video batch processing`, `fix: resolve light mode visibility`

## Workflows

### Light Mode Color Fixes
**Trigger:** When UI elements are not visible or poorly styled in light mode
**Command:** `/fix-light-mode`

1. Identify components with hardcoded dark colors (e.g., `text-gray-300`, `bg-gray-800`)
2. Replace with theme-aware Tailwind classes:
   ```tsx
   // Before
   <div className="bg-gray-800 text-gray-300">
   
   // After  
   <div className="bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-300">
   ```
3. Test visibility in both light and dark modes
4. Apply consistently across all UI components
5. Focus on cards, navigation, buttons, and form elements

### Frontend Infinite Loop Fixes
**Trigger:** When React components have infinite API calls or re-renders
**Command:** `/fix-react-loop`

1. Identify problematic useCallback/useEffect dependencies:
   ```tsx
   // Problematic - state in dependency causes loop
   const fetchData = useCallback(() => {
     // API call
   }, [someState])
   ```

2. Replace state dependencies with useRef:
   ```tsx
   const stateRef = useRef(someState)
   stateRef.current = someState
   
   const fetchData = useCallback(() => {
     // Use stateRef.current instead of someState
   }, []) // Empty dependency array
   ```

3. Update useEffect to use the fixed callback
4. Test that API calls execute once and stop looping

### Database Migration Workflow
**Trigger:** When adding new data models or extending existing ones
**Command:** `/new-migration`

1. Create new model in `backend/app/models/new_model.py`:
   ```python
   from sqlalchemy import Column, Integer, String, DateTime
   from app.database.base import Base
   
   class NewModel(Base):
       __tablename__ = "new_table"
       id = Column(Integer, primary_key=True)
       name = Column(String, nullable=False)
   ```

2. Add import to `backend/app/models/__init__.py`:
   ```python
   from .new_model import NewModel
   ```

3. Generate Alembic migration:
   ```bash
   cd backend && alembic revision --autogenerate -m "Add new_table"
   ```

4. Create corresponding Pydantic schema in `backend/app/schemas/`
5. Add API endpoints in appropriate router

### Redis Client Initialization Fix
**Trigger:** When Redis operations fail with connection or 'Job not found' errors
**Command:** `/fix-redis-client`

1. Replace module-level redis imports:
   ```python
   # Before - problematic import
   from app.database.connection import redis_client
   
   # After - function-based approach
   from app.database.connection import get_redis
   ```

2. Update all Redis operations to use fresh connections:
   ```python
   # Before
   redis_client.set(key, value)
   
   # After
   redis = get_redis()
   redis.set(key, value)
   ```

3. Ensure each operation gets a fresh Redis connection
4. Test that Redis operations work reliably

### Cache Invalidation Workflow
**Trigger:** When data updates don't reflect in UI due to stale cache
**Command:** `/add-cache-invalidation`

1. Identify write operations that affect cached data (POST, PUT, DELETE endpoints)

2. Add invalidation calls after successful database operations:
   ```python
   # After successful video update
   video = update_video(video_id, data)
   
   # Invalidate related caches
   invalidate_video_cache(video_id)
   invalidate_playlist_cache(video.playlist_id)
   ```

3. Use centralized cache invalidation helpers from `backend/app/utils/cache_invalidation.py`
4. Test that UI reflects changes immediately after mutations

### Logger Import Standardization
**Trigger:** When incorrect logging imports cause import errors or inconsistency
**Command:** `/fix-logger-imports`

1. Replace standard logging imports:
   ```python
   # Before
   import logging
   logger = logging.getLogger(__name__)
   
   # After
   from app.utils.logger import api_logger
   ```

2. Update all logger calls:
   ```python
   # Before
   logger.info("Message")
   
   # After
   api_logger.info("Message")
   ```

3. Ensure consistent logging format across all backend routers
4. Test that logging output appears correctly

## Testing Patterns

- Test files follow `*.test.*` naming pattern
- Focus on integration testing for API endpoints
- Test both success and error scenarios
- Mock external dependencies (YouTube API, Redis)

## Commands

| Command | Purpose |
|---------|---------|
| `/fix-light-mode` | Fix UI visibility issues in light theme |
| `/fix-react-loop` | Resolve infinite re-render cycles in React |
| `/new-migration` | Create database migration with new models |
| `/fix-redis-client` | Fix Redis connection issues |
| `/add-cache-invalidation` | Add cache clearing after data mutations |
| `/fix-logger-imports` | Standardize logging imports across backend |