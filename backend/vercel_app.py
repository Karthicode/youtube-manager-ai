"""Vercel serverless function handler for FastAPI app."""

# Import app first to ensure all dependencies are available
from app.main import app

try:
    from mangum import Mangum
    # Mangum is an adapter for running ASGI applications (like FastAPI) on AWS Lambda/Vercel
    # It wraps the FastAPI app to work with serverless function handlers
    handler = Mangum(app, lifespan="off")
except ImportError as e:
    # Fallback if mangum is not available (shouldn't happen in production)
    print(f"Warning: Failed to import mangum: {e}")
    print("Available packages:", __import__('sys').path)
    raise
