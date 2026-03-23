---
name: youtube-manager-ai-conventions
description: Development conventions and patterns for youtube-manager-ai. Python project with conventional commits.
---

# Youtube Manager Ai Conventions

> Generated from [Karthicode/youtube-manager-ai](https://github.com/Karthicode/youtube-manager-ai) on 2026-03-23

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
chore(deps): bump the python-minor group across 1 directory with 15 updates
```

*Commit message example*

```text
fix: bump trivy version
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
fix: clear Zustand auth state on refresh token failure to prevent infinite spinner
```

*Commit message example*

```text
fix: correct chat session cache invalidation and idempotent delete
```

*Commit message example*

```text
fix: prevent token refresh thundering herd on session expiry
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

**Frequency**: ~11 times per month

**Steps**:
1. Add feature implementation
2. Add tests for feature
3. Update documentation

**Files typically involved**:
- `frontend/app/chat/*`
- `frontend/components/*`
- `frontend/api/*`
- `**/api/**`

**Example commit sequence**:
```
feat: refactor chat streaming to use structured JSON Lines events
feat: enhance chat page with tool calls display and loading indicators
feat: add helper functions to format tool arguments and results for improved user experience
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
