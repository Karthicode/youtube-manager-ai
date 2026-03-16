---
name: youtube-manager-ai-conventions
description: Development conventions and patterns for youtube-manager-ai. Python project with conventional commits.
---

# Youtube Manager Ai Conventions

> Generated from [Karthicode/youtube-manager-ai](https://github.com/Karthicode/youtube-manager-ai) on 2026-03-16

## Overview

This skill teaches Claude the development patterns and conventions used in youtube-manager-ai.

## Tech Stack

- **Primary Language**: Python
- **Architecture**: hybrid module organization
- **Test Location**: separate

## When to Use This Skill

Activate this skill when:
- Making changes to this repository
- Adding new features following established patterns
- Writing tests that match project conventions
- Creating commits with proper message format

## Commit Conventions

Follow these commit message conventions based on 8 analyzed commits.

### Commit Style: Conventional Commits

### Prefixes Used

- `feat`
- `fix`
- `chore`
- `refactor`

### Message Guidelines

- Average message length: ~62 characters
- Keep first line concise and descriptive
- Use imperative mood ("Add feature" not "Added feature")


*Commit message example*

```text
chore(deps): bump the python-minor group across 1 directory with 13 updates
```

*Commit message example*

```text
fix: prevent token refresh thundering herd on session expiry
```

*Commit message example*

```text
feat: replace Load More button with infinite scroll in playlist detail
```

*Commit message example*

```text
refactor: replace deprecated datetime.utcnow() and add performance migrations
```

*Commit message example*

```text
perf: optimize chat agent latency with caching and adaptive reasoning
```

*Commit message example*

```text
fix: insights cards data
```

*Commit message example*

```text
feat: replace Load More button with infinite scroll
```

*Commit message example*

```text
fix: pass naive UTC datetime to google-auth Credentials expiry
```

## Architecture

### Project Structure: Single Package

This project uses **hybrid** module organization.

### Configuration Files

- `.github/workflows/backend.yml`
- `.github/workflows/claude-review.yml`
- `.github/workflows/frontend.yml`
- `.github/workflows/pr-check.yml`
- `.github/workflows/security.yml`
- `backend/vercel.json`
- `docker-compose.yml`
- `frontend/package.json`
- `frontend/tailwind.config.ts`
- `frontend/tsconfig.json`

### Guidelines

- This project uses a hybrid organization
- Follow existing patterns when adding new code

## Code Style

### Language: Python

### Naming Conventions

| Element | Convention |
|---------|------------|
| Files | camelCase |
| Functions | camelCase |
| Classes | PascalCase |
| Constants | SCREAMING_SNAKE_CASE |

### Import Style: Path Aliases (@/, ~/)

### Export Style: Default Exports


*Preferred import style*

```typescript
// Use path aliases for imports
import { Button } from '@/components/Button'
import { useAuth } from '@/hooks/useAuth'
import { api } from '@/lib/api'
```

*Preferred export style*

```typescript
// Use default exports for main component/function
export default function UserProfile() { ... }
```

## Error Handling

### Error Handling Style: Try-Catch Blocks


*Standard error handling pattern*

```typescript
try {
  const result = await riskyOperation()
  return result
} catch (error) {
  console.error('Operation failed:', error)
  throw new Error('User-friendly message')
}
```

## Common Workflows

These workflows were detected from analyzing commit patterns.

### Database Migration

Database schema changes with migration files

**Frequency**: ~2 times per month

**Steps**:
1. Create migration file
2. Update schema definitions
3. Generate/update types

**Files typically involved**:
- `**/schema.*`

**Example commit sequence**:
```
feat: refactor chat streaming to use structured JSON Lines events
feat: enhance chat page with tool calls display and loading indicators
feat: add helper functions to format tool arguments and results for improved user experience
```

### Feature Development

Standard feature implementation workflow

**Frequency**: ~13 times per month

**Steps**:
1. Add feature implementation
2. Add tests for feature
3. Update documentation

**Files typically involved**:
- `frontend/components/player/*`
- `frontend/components/*`
- `frontend/app/chat/*`
- `**/api/**`

**Example commit sequence**:
```
feat: add Vidstack player styles and improve iframe responsiveness
fix: update database URL to use local PostgreSQL instance
feat: add auto-format hook for automatic file formatting and linting
```

### Refactoring

Code refactoring and cleanup workflow

**Frequency**: ~3 times per month

**Steps**:
1. Ensure tests pass before refactor
2. Refactor code structure
3. Verify tests still pass

**Files typically involved**:
- `src/**/*`

**Example commit sequence**:
```
refactor: replace vidstack with native YouTube IFrame API for mini player
feat: redesign dashboard stats section with bar charts and top tags
fix: resolve chat sessions not loading due to re-fetch loop and blocked event loop
```

### Add Or Modify Backend Api Endpoint

Adds or modifies a backend API endpoint, often with related model/schema/service changes and sometimes a migration.

**Frequency**: ~3 times per month

**Steps**:
1. Edit or create router file in backend/app/routers/
2. Edit or create model file in backend/app/models/ if schema changes are needed
3. Edit or create schema file in backend/app/schemas/ if request/response models change
4. Edit or create service file in backend/app/services/ for business logic
5. If database schema changes, add migration in backend/alembic/versions/
6. Update backend/app/main.py if new router needs to be included

**Files typically involved**:
- `backend/app/routers/*.py`
- `backend/app/models/*.py`
- `backend/app/schemas/*.py`
- `backend/app/services/*.py`
- `backend/alembic/versions/*.py`
- `backend/app/main.py`

**Example commit sequence**:
```
Edit or create router file in backend/app/routers/
Edit or create model file in backend/app/models/ if schema changes are needed
Edit or create schema file in backend/app/schemas/ if request/response models change
Edit or create service file in backend/app/services/ for business logic
If database schema changes, add migration in backend/alembic/versions/
Update backend/app/main.py if new router needs to be included
```

### Add Or Update Database Table Or Index

Creates or modifies a database table or index, including model/schema updates and Alembic migration scripts.

**Frequency**: ~2 times per month

**Steps**:
1. Edit or create model file in backend/app/models/
2. Edit or create schema file in backend/app/schemas/ if API needs to expose new fields
3. Create Alembic migration in backend/alembic/versions/
4. Edit service or router files if logic needs to change for new fields

**Files typically involved**:
- `backend/app/models/*.py`
- `backend/app/schemas/*.py`
- `backend/alembic/versions/*.py`
- `backend/app/services/*.py`
- `backend/app/routers/*.py`

**Example commit sequence**:
```
Edit or create model file in backend/app/models/
Edit or create schema file in backend/app/schemas/ if API needs to expose new fields
Create Alembic migration in backend/alembic/versions/
Edit service or router files if logic needs to change for new fields
```

### Frontend Feature Or Ui Overhaul

Implements a new frontend feature or major UI redesign, often touching multiple components, pages, and sometimes global styles/config.

**Frequency**: ~3 times per month

**Steps**:
1. Edit or create page file in frontend/app/
2. Edit or create component in frontend/components/
3. Edit or create hook in frontend/hooks/ if needed
4. Update global styles in frontend/app/globals.css or config files
5. Edit types in frontend/types/ if new data shapes are needed

**Files typically involved**:
- `frontend/app/**/*.tsx`
- `frontend/components/**/*.tsx`
- `frontend/hooks/**/*.ts`
- `frontend/app/globals.css`
- `frontend/types/**/*.ts`

**Example commit sequence**:
```
Edit or create page file in frontend/app/
Edit or create component in frontend/components/
Edit or create hook in frontend/hooks/ if needed
Update global styles in frontend/app/globals.css or config files
Edit types in frontend/types/ if new data shapes are needed
```

### Dependency Update Backend Or Frontend

Updates dependencies in either backend or frontend, typically via automated tools or manual version bumps.

**Frequency**: ~2 times per month

**Steps**:
1. Edit dependency manifest (pyproject.toml/requirements.txt for backend, package.json/package-lock.json for frontend)
2. Update lock files (poetry.lock or package-lock.json)
3. Test for compatibility

**Files typically involved**:
- `backend/pyproject.toml`
- `backend/poetry.lock`
- `backend/requirements.txt`
- `frontend/package.json`
- `frontend/package-lock.json`

**Example commit sequence**:
```
Edit dependency manifest (pyproject.toml/requirements.txt for backend, package.json/package-lock.json for frontend)
Update lock files (poetry.lock or package-lock.json)
Test for compatibility
```

### Bugfix Frontend Or Backend

Fixes a bug in either frontend or backend, usually touching a single file or a small set of related files.

**Frequency**: ~6 times per month

**Steps**:
1. Edit the file(s) where the bug exists (component, hook, service, router, etc.)
2. Test to confirm fix

**Files typically involved**:
- `frontend/app/**/*.tsx`
- `frontend/components/**/*.tsx`
- `frontend/hooks/**/*.ts`
- `backend/app/**/*.py`

**Example commit sequence**:
```
Edit the file(s) where the bug exists (component, hook, service, router, etc.)
Test to confirm fix
```

### Add Or Update Cache Invalidation

Implements or fixes cache invalidation logic, often after backend data changes or new caching layers.

**Frequency**: ~2 times per month

**Steps**:
1. Edit or create backend/app/utils/cache_invalidation.py
2. Edit routers/services to call invalidation helpers after writes
3. Edit frontend hooks/components to use SWR or similar for cache-aware data fetching

**Files typically involved**:
- `backend/app/utils/cache_invalidation.py`
- `backend/app/routers/*.py`
- `backend/app/services/*.py`
- `frontend/hooks/**/*.ts`
- `frontend/lib/swrKeys.ts`

**Example commit sequence**:
```
Edit or create backend/app/utils/cache_invalidation.py
Edit routers/services to call invalidation helpers after writes
Edit frontend hooks/components to use SWR or similar for cache-aware data fetching
```


## Best Practices

Based on analysis of the codebase, follow these practices:

### Do

- Use conventional commit format (feat:, fix:, etc.)
- Use camelCase for file names
- Prefer default exports

### Don't

- Don't use long relative imports (use aliases)
- Don't write vague commit messages
- Don't deviate from established patterns without discussion

---

*This skill was auto-generated by [ECC Tools](https://ecc.tools). Review and customize as needed for your team.*
