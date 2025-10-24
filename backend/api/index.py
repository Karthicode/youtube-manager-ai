"""Vercel serverless function handler for FastAPI app."""

import sys
from pathlib import Path

# Add parent directory to path so we can import from app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app
from mangum import Mangum

# Mangum adapter for Vercel
handler = Mangum(app, lifespan="off")
