# youtube-manager-ai Development Patterns

> Auto-generated skill from repository analysis

## Overview

This skill covers development patterns for a YouTube Manager AI application - a full-stack Python/TypeScript application for managing YouTube content with AI capabilities. The codebase follows conventional commit patterns, uses FastAPI for the backend with Alembic migrations, and React/Next.js for the frontend with a focus on chat functionality and playlist management.

## Coding Conventions

### File Naming
- **Backend**: snake_case for Python files (`chat_service.py`, `video_models.py`)
- **Frontend**: camelCase for TypeScript files (`VideoCard.tsx`, `chatPage.tsx`)

### Import Style
```python
# Backend - Use aliases
from backend.app.models import video as video_models
from backend.app.schemas import chat as chat_schemas
```

```typescript
// Frontend - Default exports preferred
import VideoCard from '@/components/VideoCard'
import { ChatResponse } from '@/types/index'
```

### Commit Patterns
- Use conventional commits with prefixes: `feat:`, `fix:`, `refactor:`, `chore:`
- Keep messages around 63 characters
- Example: `feat: add chat streaming functionality with session mgmt`

## Workflows

### Fix UI Colors for Light Mode
**Trigger:** When components have hardcoded dark colors or poor light mode visibility
**Command:** `/fix-light-mode`

1. **Identify problematic components** - Look for hardcoded color values like `bg-gray-800`, `text-white`
2. **Replace with theme-aware classes** - Use Tailwind's dark mode utilities or CSS variables
3. **Update component files** focusing on:
   - `frontend/components/VideoCard.tsx`
   - `frontend/app/chat/page.tsx` 
   - `frontend/components/Navbar.tsx`
4. **Test visibility** in both light and dark modes

```tsx
// Before
<div className="bg-gray-800 text-white">

// After  
<div className="bg-gray-800 dark:bg-gray-800 bg-white text-gray-900 dark:text-white">
```

### Add Database Model with Migration
**Trigger:** When adding new data persistence requirements
**Command:** `/add-model`

1. **Create Alembic migration** in `backend/alembic/versions/`
```python
def upgrade():
    op.create_table('chat_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )
```

2. **Add model class** to `backend/app/models/`
```python
class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(Integer, primary_key=True)
    user_id = Column(String(50), nullable=False)
```

3. **Update models/__init__.py** to include new import
4. **Create Pydantic schemas** in `backend/app/schemas/`
5. **Add database service layer** if complex queries needed

### Fix Infinite Rerender Loops
**Trigger:** When components have cascading re-renders or network request loops
**Command:** `/fix-rerender-loop`

1. **Identify problematic dependencies** in useEffect/useCallback hooks
2. **Replace state dependencies with refs** where state changes shouldn't trigger effects
```tsx
// Before
const fetchData = useCallback(() => {
  // fetch logic
}, [someState, anotherState])

// After
const fetchData = useCallback(() => {
  // fetch logic  
}, [someStateRef.current, stableValue])
```

3. **Break re-creation cycles** by memoizing callback functions properly
4. **Test that infinite loops are resolved** - check Network tab for repeated requests

### Enhance Chat Functionality
**Trigger:** When extending chat capabilities or fixing chat issues
**Command:** `/enhance-chat`

1. **Update backend chat router** (`backend/app/routers/chat.py`)
```python
@router.post("/stream")
async def stream_chat(request: ChatRequest):
    return StreamingResponse(agent_service.stream_response(request.message))
```

2. **Modify chat schemas** if new data structures needed
3. **Update frontend chat page** (`frontend/app/chat/page.tsx`) with new UI elements
4. **Add new API endpoints** and integrate with agent service
5. **Test streaming and session functionality** end-to-end

### Add API Router with Main Integration
**Trigger:** When adding new API endpoints or feature areas
**Command:** `/add-api-router`

1. **Create new router file** in `backend/app/routers/`
```python
from fastapi import APIRouter
router = APIRouter(prefix="/playlists", tags=["playlists"])

@router.get("/")
async def get_playlists():
    return {"playlists": []}
```

2. **Add router to main.py**
```python
from backend.app.routers import playlists
app.include_router(playlists.router)
```

3. **Create frontend API client functions** in `frontend/api/api.ts`
4. **Add TypeScript types** in `frontend/types/index.ts` if needed

### Fix Configuration and Imports
**Trigger:** When there are import errors, config issues, or dependency problems
**Command:** `/fix-config`

1. **Identify the configuration issue** - check error messages and stack traces
2. **Update relevant config files**:
   - `frontend/tsconfig.json` for TypeScript path resolution
   - `frontend/biome.json` for linting rules
   - `backend/app/config.py` for environment variables
3. **Fix import statements** - ensure proper relative/absolute paths
4. **Test that errors are resolved** - run build/dev commands

## Testing Patterns

- Test files follow the pattern `*.test.*`
- Testing framework not clearly detected, likely Jest for frontend and pytest for backend
- Focus on testing workflows end-to-end, especially chat streaming and database operations

## Commands

| Command | Purpose |
|---------|---------|
| `/fix-light-mode` | Fix UI component color schemes for light mode compatibility |
| `/add-model` | Add new database table/model with Alembic migration and schemas |
| `/fix-rerender-loop` | Fix React useEffect/useCallback dependency issues causing infinite loops |
| `/enhance-chat` | Add or improve chat-related features including UI and streaming |
| `/add-api-router` | Add new API router and integrate it into main FastAPI application |
| `/fix-config` | Fix configuration files, imports, and dependency issues |