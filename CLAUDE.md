# YouTube Manager AI - Development Guidelines

## Project Overview

YouTube Manager AI is a web application for managing and organizing YouTube liked videos with AI-powered categorization. The system allows users to:
- Authenticate with YouTube and import liked videos
- Automatically categorize videos using OpenAI
- Create custom playlists and filter videos by tags
- Track video statistics and engagement

**Tech Stack:**
- **Backend:** FastAPI, SQLAlchemy, PostgreSQL, Redis, OpenAI
- **Frontend:** Next.js 16 (App Router), Zustand, Tailwind CSS, HeroUI, TypeScript
- **Authentication:** JWT tokens with OAuth2 (YouTube)

---

## Development Workflow Commands

### Backend Commands

```bash
# Development server
cd backend
python -m uvicorn app.main:app --reload

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "description"

# Code quality (RUN AFTER EVERY CHANGE)
black .              # Format code
ruff check .         # Lint
mypy .              # Type checking

# Combined quality check
black . && ruff check . && mypy .

# Testing
pytest
pytest --cov
pytest -v -s  # Verbose with output
```

### Frontend Commands

```bash
# Development server
cd frontend
bun run dev

# Code quality (RUN AFTER EVERY CHANGE)
bun run check:fix    # Format + Lint (auto-fix)
bun run typecheck    # Type checking

# Combined quality check
bun run check:fix && bun run typecheck

# Production
bun run build
bun run start
```

---

## Code Quality Requirements

**CRITICAL:** Always run formatting and linting after every code change. This is mandatory before committing any code.

### Backend Quality Pipeline
1. **Black** - Code formatting (auto-fix)
2. **Ruff** - Fast Python linter (check for issues)
3. **MyPy** - Static type checking

### Frontend Quality Pipeline
1. **Biome** - Format and lint (auto-fix)
2. **TypeScript** - Type checking

### Pre-Commit Checklist
- [ ] Run formatting and linting commands
- [ ] All quality checks pass
- [ ] No type errors
- [ ] Code builds successfully
- [ ] Write descriptive commit message

---

## Backend Architecture Guidelines

### FastAPI Best Practices

**Async Operations:**
- Use `async`/`await` for all database operations
- Use `async`/`await` for external API calls (YouTube, OpenAI)
- Leverage asyncio for concurrent operations

**Dependency Injection:**
```python
from fastapi import Depends
from app.dependencies import get_db, get_current_user

@router.get("/videos")
async def get_videos(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Implementation
```

**Architecture Pattern:**
- **Router** → **Service** → **Model** separation
- Routers handle HTTP concerns (requests/responses)
- Services contain business logic
- Models define database schema

**Pydantic Models:**
- Use Pydantic for request/response validation
- Define separate schemas for create, update, and response
- Never return raw ORM objects from endpoints

**Lifespan Events:**
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await initialize_database()
    yield
    # Shutdown
    await cleanup_resources()
```

### Database Patterns

**SQLAlchemy 2.0+ Usage:**
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

async def get_videos(db: AsyncSession, user_id: int):
    result = await db.execute(
        select(Video).where(Video.user_id == user_id)
    )
    return result.scalars().all()
```

**Best Practices:**
- Use composite indexes for frequently queried columns
- Implement soft deletes where appropriate (e.g., playlists)
- Always use `Session` dependency injection
- Use async session management with context managers
- Avoid N+1 queries - use `selectinload()` or `joinedload()`

**Index Examples:**
```python
__table_args__ = (
    Index('idx_user_video', 'user_id', 'video_id'),
    Index('idx_created_at', 'created_at'),
)
```

### Error Handling

**HTTPException Usage:**
```python
from fastapi import HTTPException

if not video:
    raise HTTPException(
        status_code=404,
        detail="Video not found"
    )
```

**Logging:**
```python
from app.utils.logger import app_logger, api_logger

try:
    result = await process_videos()
except Exception as e:
    app_logger.error(f"Failed to process videos: {e}", exc_info=True)
    raise HTTPException(status_code=500, detail="Processing failed")
```

**Error Categories:**
- 400: Bad Request (validation errors)
- 401: Unauthorized (auth required)
- 403: Forbidden (insufficient permissions)
- 404: Not Found
- 500: Internal Server Error

### API Design

**Route Structure:**
- All routes prefixed with `/api/v1`
- Use RESTful conventions
- Group related endpoints under routers

**Pagination:**
```python
@router.get("/videos")
async def list_videos(
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db)
):
    offset = (page - 1) * page_size
    # Return paginated results
```

**Filtering:**
- Support filtering via query parameters
- Use Pydantic models for filter validation
- Implement flexible filtering (tags, playlists, date ranges)

**Server-Sent Events (SSE):**
```python
from fastapi.responses import StreamingResponse

@router.get("/sync")
async def sync_videos():
    async def event_stream():
        yield f"data: {json.dumps({'progress': 50})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream"
    )
```

### Authentication

**JWT Implementation:**
- Access tokens: 30 minutes expiry
- Refresh tokens: 7 days expiry
- Store tokens in Redis for revocation support

**Protected Routes:**
```python
from app.dependencies import get_current_user

@router.get("/profile")
async def get_profile(
    current_user: User = Depends(get_current_user)
):
    return current_user
```

**Token Refresh:**
- Frontend automatically refreshes tokens on 401 errors
- Implement refresh endpoint at `/api/v1/auth/refresh`
- Validate refresh token and issue new access token

---

## Frontend Architecture Guidelines

### Next.js App Router Best Practices

**Server vs Client Components:**
- Use Server Components by default
- Use Client Components (`"use client"`) only when needed:
  - Event handlers (onClick, onChange, etc.)
  - State management (useState, useReducer)
  - Browser APIs (localStorage, window)
  - Third-party libraries that require client-side

**Route Organization:**
```
app/
├── (auth)/           # Route group for auth pages
│   ├── login/
│   └── callback/
├── (dashboard)/      # Route group for main app
│   ├── layout.tsx    # Shared layout
│   ├── page.tsx      # Dashboard home
│   ├── videos/
│   └── playlists/
└── api/              # API routes (if needed)
```

**Dynamic Routes:**
```typescript
// app/playlists/[id]/page.tsx
interface PageProps {
  params: { id: string }
}

export default function PlaylistPage({ params }: PageProps) {
  // Implementation
}
```

**Loading and Error States:**
```typescript
// app/videos/loading.tsx
export default function Loading() {
  return <Spinner />
}

// app/videos/error.tsx
export default function Error({ error }: { error: Error }) {
  return <ErrorDisplay message={error.message} />
}
```

### State Management

**Zustand for Global State:**
```typescript
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AuthState {
  token: string | null
  user: User | null
  setToken: (token: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      setToken: (token) => set({ token }),
      logout: () => set({ token: null, user: null })
    }),
    { name: 'auth-storage' }
  )
)
```

**Local Component State:**
- Use `useState` for UI-specific state
- Use `useReducer` for complex state logic
- Keep state as local as possible

**Hydration Considerations:**
```typescript
// Prevent hydration mismatches
const [mounted, setMounted] = useState(false)

useEffect(() => {
  setMounted(true)
}, [])

if (!mounted) return null
```

### Component Patterns

**File Naming:**
- PascalCase for all components: `VideoCard.tsx`
- camelCase for utilities: `apiClient.ts`
- kebab-case for CSS modules: `video-card.module.css`

**Component Structure:**
```typescript
import { ReactNode } from 'react'

interface VideoCardProps {
  video: Video
  onLike?: () => void
  children?: ReactNode
}

export function VideoCard({ video, onLike, children }: VideoCardProps) {
  return (
    // Implementation
  )
}
```

**HeroUI Components:**
- Use HeroUI for consistent UI (Button, Card, Modal, etc.)
- Follow HeroUI theming patterns
- Leverage built-in accessibility features

**Accessibility:**
- Include proper ARIA labels
- Ensure keyboard navigation works
- Maintain WCAG AA contrast ratios
- Use semantic HTML elements

### API Integration

**Centralized Axios Instance:**
```typescript
// lib/apiClient.ts
import axios from 'axios'

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  headers: { 'Content-Type': 'application/json' }
})

// Request interceptor - add auth token
apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor - handle token refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Attempt token refresh
      await refreshToken()
      // Retry original request
      return apiClient.request(error.config)
    }
    return Promise.reject(error)
  }
)
```

**API Call Pattern:**
```typescript
async function fetchVideos() {
  try {
    setLoading(true)
    const response = await apiClient.get('/videos')
    setVideos(response.data)
  } catch (error) {
    console.error('Failed to fetch videos:', error)
    setError('Failed to load videos')
  } finally {
    setLoading(false)
  }
}
```

**Server-Sent Events:**
```typescript
const eventSource = new EventSource(
  `${API_URL}/sync?token=${token}`
)

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data)
  setProgress(data.progress)
}

eventSource.onerror = () => {
  eventSource.close()
}
```

### Styling with Tailwind CSS

**Utility-First Approach:**
```tsx
<div className="flex items-center gap-4 p-4 rounded-lg bg-white dark:bg-gray-800">
  <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
    Title
  </h2>
</div>
```

**CSS Variables for Theming:**
```css
:root {
  --primary: #3b82f6;
  --background: #ffffff;
  --foreground: #000000;
}

[data-theme="dark"] {
  --background: #000000;
  --foreground: #ffffff;
}
```

**Responsive Design:**
```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  {/* Content */}
</div>
```

**HeroUI Integration:**
- Use HeroUI's built-in theming system
- Leverage color scales (primary, secondary, etc.)
- Use semantic color tokens for consistency

---

## Testing Guidelines

### Backend Testing

**Setup (pytest + pytest-asyncio):**
```python
# tests/conftest.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with AsyncSession(engine) as session:
        yield session
```

**Test Patterns:**
```python
@pytest.mark.asyncio
async def test_create_video(db_session):
    video = Video(title="Test", video_id="abc123")
    db_session.add(video)
    await db_session.commit()

    result = await db_session.get(Video, video.id)
    assert result.title == "Test"
```

**Mocking External APIs:**
```python
from unittest.mock import patch, AsyncMock

@patch('app.services.youtube.fetch_videos')
async def test_sync_videos(mock_fetch, db_session):
    mock_fetch.return_value = [{"id": "123", "title": "Test"}]
    result = await sync_videos(db_session, user_id=1)
    assert len(result) == 1
```

### Frontend Testing

**Setup (Jest + React Testing Library):**
```typescript
import { render, screen } from '@testing-library/react'
import { VideoCard } from './VideoCard'

describe('VideoCard', () => {
  it('renders video title', () => {
    const video = { id: '1', title: 'Test Video' }
    render(<VideoCard video={video} />)
    expect(screen.getByText('Test Video')).toBeInTheDocument()
  })
})
```

**Testing Async Operations:**
```typescript
import { waitFor } from '@testing-library/react'

it('loads videos on mount', async () => {
  render(<VideoList />)
  await waitFor(() => {
    expect(screen.getByText('Video 1')).toBeInTheDocument()
  })
})
```

---

## Git Workflow

### Commit Guidelines

**Pre-Commit Checklist:**
1. Run `black . && ruff check . && mypy .` (backend)
2. Run `bun run check:fix && bun run typecheck` (frontend)
3. Ensure all quality checks pass
4. Test the changes locally

**Commit Message Format:**
```
<type>: <description>

[optional body]

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code refactoring
- `docs`: Documentation changes
- `test`: Adding tests
- `chore`: Maintenance tasks

**Examples:**
```
feat: add bulk dislike functionality

Implemented bulk dislike API endpoint and dialog box in filter panel.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### Branch Strategy

- **Main branch:** `main` (production-ready code)
- **Feature branches:** `feat/feature-name`
- **Bug fixes:** `fix/bug-description`
- **Refactoring:** `refactor/what-changed`

**Workflow:**
1. Create feature branch from `main`
2. Make changes with proper formatting/linting
3. Commit with descriptive messages
4. Push to remote
5. Create pull request to `main`

---

## Environment Configuration

### Backend (.env)

```bash
# Environment
ENVIRONMENT=local  # local, staging, production

# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/youtube_manager

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# YouTube OAuth
YOUTUBE_CLIENT_ID=your-client-id.apps.googleusercontent.com
YOUTUBE_CLIENT_SECRET=your-client-secret
YOUTUBE_REDIRECT_URI=http://localhost:3000/callback

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000

# Logging
LOG_LEVEL=INFO
```

### Frontend (.env.local)

```bash
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1

# YouTube OAuth (must match backend)
NEXT_PUBLIC_YOUTUBE_CLIENT_ID=your-client-id.apps.googleusercontent.com
NEXT_PUBLIC_YOUTUBE_REDIRECT_URI=http://localhost:3000/callback
```

**Security Notes:**
- Never commit `.env` files to git
- Use `.env.example` for documentation
- Rotate secrets regularly
- Use different secrets for each environment

---

## Performance Optimization

### Backend Optimization

**Redis Caching:**
```python
import json
from app.config import redis_client

async def get_video_stats(user_id: int):
    cache_key = f"stats:{user_id}"
    cached = await redis_client.get(cache_key)

    if cached:
        return json.loads(cached)

    stats = await calculate_stats(user_id)
    await redis_client.setex(cache_key, 300, json.dumps(stats))  # 5 min TTL
    return stats
```

**Database Optimization:**
- Use indexes on frequently queried columns
- Implement connection pooling
- Batch operations where possible
- Use `select_in_loading` to prevent N+1 queries

**AI Categorization Batching:**
```python
# Batch 10 videos per AI call
BATCH_SIZE = 10
for i in range(0, len(videos), BATCH_SIZE):
    batch = videos[i:i + BATCH_SIZE]
    await categorize_batch(batch)
```

**Async Concurrency:**
```python
import asyncio

tasks = [process_video(video) for video in videos]
results = await asyncio.gather(*tasks)
```

### Frontend Optimization

**Code Splitting:**
```typescript
import dynamic from 'next/dynamic'

const VideoPlayer = dynamic(() => import('./VideoPlayer'), {
  loading: () => <Spinner />,
  ssr: false
})
```

**Image Optimization:**
```tsx
import Image from 'next/image'

<Image
  src={thumbnail}
  alt={title}
  width={320}
  height={180}
  loading="lazy"
/>
```

**Pagination:**
- Implement virtual scrolling for large lists
- Use cursor-based pagination for better performance
- Load data incrementally (infinite scroll)

**Server-Sent Events:**
- Use SSE instead of polling for real-time updates
- Reduces server load and network traffic
- Better user experience for long operations

**Bundle Optimization:**
- Import only what you need from libraries
- Use tree-shaking effectively
- Analyze bundle size with `bun run analyze`

---

## Security Best Practices

### Backend Security

**Environment Variables:**
- Never hardcode secrets
- Use `.env` files (excluded from git)
- Validate all environment variables on startup

**CORS Configuration:**
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Input Validation:**
- Use Pydantic for all inputs
- Validate types, ranges, and formats
- Sanitize user-provided strings

**SQL Injection Prevention:**
- Always use SQLAlchemy ORM (parameterized queries)
- Never concatenate SQL strings
- Use bind parameters for raw queries

**Rate Limiting:**
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/api/v1/videos")
@limiter.limit("100/minute")
async def get_videos():
    pass
```

**Token Security:**
- Store tokens in Redis with expiry
- Implement token revocation
- Rotate refresh tokens on use
- Use secure random generation

### Frontend Security

**Token Storage:**
```typescript
// Store in localStorage (acceptable for this app)
localStorage.setItem('token', accessToken)

// Clear on logout
localStorage.removeItem('token')
```

**CSRF Protection:**
- Use SameSite cookies if using cookies
- Include CSRF tokens for state-changing operations
- Validate Origin header on backend

**Input Sanitization:**
```typescript
import DOMPurify from 'isomorphic-dompurify'

const clean = DOMPurify.sanitize(userInput)
```

**HTTPS in Production:**
- Always use HTTPS in production
- Set secure headers (HSTS, CSP, etc.)
- Implement proper certificate management

**Authentication Guards:**
```typescript
// middleware.ts
export function middleware(request: NextRequest) {
  const token = request.cookies.get('token')

  if (!token && !request.nextUrl.pathname.startsWith('/login')) {
    return NextResponse.redirect(new URL('/login', request.url))
  }
}
```

---

## Common Patterns and Solutions

### Backend Patterns

**Bulk Operations:**
```python
async def bulk_update_videos(video_ids: list[int], user_id: int):
    stmt = (
        update(Video)
        .where(Video.id.in_(video_ids))
        .where(Video.user_id == user_id)
        .values(updated_at=func.now())
    )
    await db.execute(stmt)
    await db.commit()
```

**Soft Deletes:**
```python
class Playlist(Base):
    deleted_at = Column(DateTime, nullable=True)

    @property
    def is_deleted(self):
        return self.deleted_at is not None

# Query only non-deleted
query = select(Playlist).where(Playlist.deleted_at.is_(None))
```

**Progress Tracking with SSE:**
```python
async def sync_with_progress(user_id: int):
    async def event_generator():
        total = await count_videos()
        for i, video in enumerate(fetch_videos()):
            await process_video(video)
            progress = int((i + 1) / total * 100)
            yield f"data: {json.dumps({'progress': progress})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### Frontend Patterns

**Loading States:**
```typescript
function VideoList() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [videos, setVideos] = useState<Video[]>([])

  if (loading) return <Spinner />
  if (error) return <ErrorDisplay message={error} />
  if (videos.length === 0) return <EmptyState />

  return <VideoGrid videos={videos} />
}
```

**Optimistic Updates:**
```typescript
async function likeVideo(videoId: string) {
  // Update UI immediately
  setVideos(prev => prev.map(v =>
    v.id === videoId ? { ...v, liked: true } : v
  ))

  try {
    await apiClient.post(`/videos/${videoId}/like`)
  } catch (error) {
    // Revert on error
    setVideos(prev => prev.map(v =>
      v.id === videoId ? { ...v, liked: false } : v
    ))
  }
}
```

**Debounced Search:**
```typescript
import { useDebouncedCallback } from 'use-debounce'

const debouncedSearch = useDebouncedCallback(
  (query: string) => {
    fetchVideos({ search: query })
  },
  500
)
```

---

## Troubleshooting

### Common Issues

**Database Connection Errors:**
- Check DATABASE_URL in .env
- Ensure PostgreSQL is running
- Verify connection pooling settings

**Redis Connection Errors:**
- Check REDIS_URL in .env
- Ensure Redis is running
- Test with `redis-cli ping`

**CORS Errors:**
- Verify ALLOWED_ORIGINS in backend .env
- Check NEXT_PUBLIC_API_URL in frontend .env
- Ensure middleware is configured correctly

**Type Errors:**
- Run `mypy .` in backend
- Run `bun run typecheck` in frontend
- Check for any `any` types that need fixing

**Authentication Issues:**
- Verify JWT_SECRET_KEY matches between services
- Check token expiry times
- Ensure refresh token logic works

### Debugging Tips

**Backend:**
- Use `app_logger.debug()` for detailed logging
- Enable SQLAlchemy query logging in development
- Use `pytest -vv -s` for verbose test output

**Frontend:**
- Use React DevTools for component inspection
- Check Network tab for API call failures
- Use `console.log` strategically (remove before commit)

---

## Additional Resources

### Documentation
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Next.js Documentation](https://nextjs.org/docs)
- [Zustand Documentation](https://zustand-demo.pmnd.rs/)
- [HeroUI Documentation](https://www.heroui.com/)

### Tools
- [Ruff](https://docs.astral.sh/ruff/) - Fast Python linter
- [Black](https://black.readthedocs.io/) - Python code formatter
- [Biome](https://biomejs.dev/) - Fast web development toolchain
- [Alembic](https://alembic.sqlalchemy.org/) - Database migrations

---

## Maintenance

This CLAUDE.md file should be updated when:
- New major features are added
- Development workflows change
- New tools or dependencies are introduced
- Best practices evolve
- Common issues are discovered

Keep this document as the single source of truth for development guidelines in this project.
