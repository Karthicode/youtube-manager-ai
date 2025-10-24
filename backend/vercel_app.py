"""Vercel serverless function handler for FastAPI app."""

from mangum import Mangum
from app.main import app

# Mangum is an adapter for running ASGI applications (like FastAPI) on AWS Lambda/Vercel
# It wraps the FastAPI app to work with serverless function handlers
handler = Mangum(app, lifespan="off")
