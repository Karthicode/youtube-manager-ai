"""Vercel serverless function handler for FastAPI app."""

from app.main import app

# Vercel expects a variable named 'app' or a function named 'handler'
# This file serves as the entry point for Vercel's Python runtime
