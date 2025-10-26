#!/bin/bash
# Run database migrations
cd "$(dirname "$0")/.."
python -m alembic upgrade head
