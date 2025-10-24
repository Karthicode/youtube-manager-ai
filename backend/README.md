# YouTube Manager Backend

Backend service for the YouTube Manager AI application.

## Setup

1. Install dependencies:
   ```bash
   poetry install
   ```

2. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. Run migrations:
   ```bash
   alembic upgrade head
   ```

4. Start the server:
   ```bash
   uvicorn app.main:app --reload
   ```
