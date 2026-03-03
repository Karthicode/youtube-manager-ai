# YouTube Manager AI

A full-stack application for managing YouTube liked videos and playlists with AI-powered categorization, semantic search, and analytics. Authenticate with YouTube, import your library, and let OpenAI organize everything automatically.

## Features

- **YouTube OAuth & Import** - Authenticate and sync liked videos, playlists, and channel data
- **AI Categorization** - Automatic video categorization using OpenAI (gpt-4.1-mini) with confidence scoring
- **Intelligent Tag Generation** - AI-generated tags per video for improved discovery
- **Semantic Search** - Vector-based search powered by pgvector embeddings
- **Watch Later Management** - Track and manage videos to watch later
- **Analytics & Insights** - Dashboard with engagement stats, category breakdowns, and channel recommendations
- **Playlist Creation** - Create custom playlists from filtered video sets
- **Bulk Operations** - Batch categorize, delete, or manage videos by tags/categories
- **Real-Time Progress** - Server-Sent Events for live sync and categorization progress
- **Advanced Filtering & Sorting** - Filter by category, tags, date, duration; sort by multiple criteria
- **Dark/Light Theme** - Full theme support via next-themes and HeroUI
- **Background Jobs** - Async task processing with QStash

## Tech Stack

**Backend:** FastAPI, PostgreSQL, Redis, SQLAlchemy 2.0, Alembic, OpenAI SDK, pgvector, QStash

**Frontend:** Next.js 16, React 19, TypeScript, HeroUI, Tailwind CSS 4, Zustand, SWR, Visx, Framer Motion

**Infrastructure:** Docker Compose, Kubernetes, GitHub Actions CI/CD

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 22+
- Docker and Docker Compose
- Poetry

### 1. Start Infrastructure

```bash
docker-compose up -d  # PostgreSQL + Redis
```

### 2. Backend Setup

```bash
cd backend
poetry install
cp .env.example .env  # Edit with your YouTube, OpenAI, and JWT credentials
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload
```

### 3. Frontend Setup

```bash
cd frontend
npm install
cp .env.example .env.local  # Set NEXT_PUBLIC_API_URL
npm run dev
```

### 4. Access

- **App:** <http://localhost:3000>
- **API docs:** <http://localhost:8000/api/v1/docs>

## Development

### Backend

```bash
cd backend
black . && ruff check . && mypy .
```

Remote Supabase migration workflow (Alembic + Supabase CLI):
- See `docs/supabase-alembic-migration-workflow.md`

### Frontend

```bash
cd frontend
npm run check:fix && npm run typecheck
```

## Project Structure

```text
backend/app/
├── models/          # SQLAlchemy models (User, Video, Playlist, Category, Tag, ...)
├── routers/         # FastAPI route handlers
├── services/        # Business logic (AI, YouTube, Auth)
├── schemas/         # Pydantic request/response schemas
├── utils/           # Logging, helpers
├── config.py        # Pydantic Settings configuration
├── database.py      # Async database connection
├── dependencies.py  # Dependency injection (auth, db session)
└── main.py          # FastAPI app entrypoint

frontend/
├── app/             # Next.js App Router (auth, dashboard, videos, playlists, insights, settings)
├── components/      # UI components (VideoCard, FilterPanel, Navbar, insights/)
├── store/           # Zustand state management
├── api/             # API client and hooks
└── hooks/           # Custom React hooks
```

## API Documentation

Interactive docs are available at `/api/v1/docs` when the backend is running.

**Route groups:** auth, videos, playlists, categories, tags, insights, progress, worker

## Environment Variables

See `backend/.env.example` and `frontend/.env.example` for all required configuration.

## License

MIT
