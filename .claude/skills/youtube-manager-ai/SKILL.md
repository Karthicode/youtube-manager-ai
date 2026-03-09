# youtube-manager-ai Development Patterns

> Auto-generated skill from repository analysis

## Overview

The youtube-manager-ai repository is a Python-based application for managing YouTube content with AI assistance. It follows a clean architecture with separate backend and frontend components, using FastAPI for the API layer, SQLAlchemy for database operations, and React for the frontend. The codebase emphasizes consistent patterns for API development, database migrations, and Redis-based job processing.

## Coding Conventions

### File Naming
- **Python files**: Use camelCase naming convention
- **Test files**: Follow `*.test.*` pattern
- **Migration files**: Timestamped Alembic format in `backend/alembic/versions/`

### Import Style
```python
# Use alias imports for common modules
from app.core.database import get_redis
from app.models import User as UserModel
from app.schemas import UserSchema
```

### Commit Messages
- **Format**: Conventional commits with prefixes
- **Prefixes**: `feat`, `fix`, `chore`, `refactor`
- **Length**: Average 66 characters
- **Example**: `feat: add user preference endpoint for video filtering`

### Code Structure
```python
# Router structure
from fastapi import APIRouter, Depends
from app.core.logging import api_logger

router = APIRouter()

@router.get("/endpoint")
async def endpoint_function():
    api_logger.info("Processing request")
    return {"status": "success"}
```

## Workflows

### Dependency Updates
**Trigger:** When dependabot detects outdated packages
**Command:** `/update-deps`

1. Update `backend/pyproject.toml` with new package versions
2. Regenerate `backend/poetry.lock` file using Poetry
3. Update `backend/requirements.txt` to match pyproject.toml
4. Test application startup and key functionality
5. Commit with message: `chore: update dependencies to latest versions`

### Redis Client Fixes
**Trigger:** When encountering Redis connection issues or 'Job not found in Redis' errors
**Command:** `/fix-redis-client`

1. Identify files using module-level `redis_client` imports
2. Replace imports with `get_redis()` function calls:
   ```python
   # Before
   from app.core.database import redis_client
   
   # After  
   from app.core.database import get_redis
   
   # Usage
   redis = get_redis()
   result = redis.get(key)
   ```
3. Update all Redis operations to use fresh client instances
4. Test Redis connectivity and job processing
5. Commit with message: `fix: use get_redis() function for fresh connections`

### Logging Fixes
**Trigger:** When fixing inconsistent logging imports or formatting issues
**Command:** `/fix-logging`

1. Identify incorrect logger imports in router files
2. Replace with correct api_logger import:
   ```python
   # Incorrect
   import logging
   
   # Correct
   from app.core.logging import api_logger
   ```
3. Update logger usage patterns throughout the file
4. Fix any code formatting issues
5. Test logging output in development
6. Commit with message: `fix: correct logger imports and formatting`

### Security Improvements
**Trigger:** When improving security posture or adding new security measures
**Command:** `/add-security-scan`

1. Add or update `.github/workflows/security.yml` with security scanning
2. Configure Semgrep rules in `.semgrep.yml`
3. Update authentication mechanisms in worker routes
4. Add security headers and validation
5. Update PR check workflows to include security scans
6. Test security measures in staging environment
7. Commit with message: `feat: enhance security scanning and authentication`

### Database Migrations
**Trigger:** When adding new database tables or columns for features
**Command:** `/add-migration`

1. Create new Alembic migration file:
   ```bash
   alembic revision --autogenerate -m "add user preferences table"
   ```
2. Update SQLAlchemy models in `backend/app/models/`:
   ```python
   class UserPreference(Base):
       __tablename__ = "user_preferences"
       id = Column(Integer, primary_key=True)
       user_id = Column(Integer, ForeignKey("users.id"))
   ```
3. Update model imports in `backend/app/models/__init__.py`
4. Create corresponding Pydantic schemas in `backend/app/schemas/`
5. Test migration up and down operations
6. Commit with message: `feat: add user preferences database migration`

### API Endpoint Development
**Trigger:** When implementing new backend functionality accessible from frontend
**Command:** `/add-api-endpoint`

1. Create new router endpoint in appropriate file:
   ```python
   @router.post("/preferences")
   async def create_preference(preference: PreferenceCreate):
       api_logger.info("Creating user preference")
       return {"id": 1, "status": "created"}
   ```
2. Add router to `backend/app/main.py`:
   ```python
   app.include_router(preferences_router, prefix="/api/preferences")
   ```
3. Update frontend API client in `frontend/api/api.ts`
4. Add TypeScript types in `frontend/types/index.ts`
5. Update UI components to use new endpoint
6. Test end-to-end functionality
7. Commit with message: `feat: add preferences API endpoint with frontend integration`

### Frontend Component Updates
**Trigger:** When adding new features or improving existing UI components
**Command:** `/update-component`

1. Update React component logic in `frontend/components/` or `frontend/app/`
2. Add new props, state, or hooks as needed
3. Update TypeScript interfaces in `frontend/types/index.ts`
4. Integrate with backend API endpoints
5. Test component rendering and interactions
6. Update parent components if necessary
7. Commit with message: `feat: enhance component with new functionality`

## Testing Patterns

### Test File Structure
- Test files follow the `*.test.*` naming pattern
- Tests are co-located with source files or in dedicated test directories
- Framework detection is automatic but patterns suggest Jest/pytest usage

### Testing Best Practices
```python
# Example test structure for API endpoints
def test_create_preference():
    # Arrange
    preference_data = {"key": "value"}
    
    # Act
    response = client.post("/api/preferences", json=preference_data)
    
    # Assert
    assert response.status_code == 201
    assert response.json()["status"] == "created"
```

## Commands

| Command | Purpose |
|---------|---------|
| `/update-deps` | Update Python dependencies across pyproject.toml, poetry.lock, and requirements.txt |
| `/fix-redis-client` | Replace redis_client imports with get_redis() function calls |
| `/fix-logging` | Correct logger imports from logging to api_logger |
| `/add-security-scan` | Add or enhance security scanning workflows and configurations |
| `/add-migration` | Create database migration with corresponding models and schemas |
| `/add-api-endpoint` | Create new API endpoint with full frontend integration |
| `/update-component` | Update React components with new functionality and TypeScript types |