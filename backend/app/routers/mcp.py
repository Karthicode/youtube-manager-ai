"""MCP router with API key authentication middleware.

Wraps the FastMCP ASGI app with API key validation so that
MCP clients (Claude Desktop, Cursor, etc.) authenticate via Bearer token.
"""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.database import SessionLocal
from app.logger import api_logger
from app.mcp_server import current_user_id, mcp_server
from app.models.user import User


class McpApiKeyAuthMiddleware(BaseHTTPMiddleware):
    """Middleware that validates API key and sets the current user context."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        # Extract API key from Authorization header (Bearer <key>)
        auth_header = request.headers.get("authorization", "")
        api_key: str | None = None

        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]

        # Also support query param for clients that can't set headers
        if not api_key:
            api_key = request.query_params.get("api_key")

        if not api_key:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Missing API key. Provide via Authorization: Bearer <key> header."
                },
            )

        # Look up user by API key
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.api_key == api_key).first()
            if not user:
                return JSONResponse(
                    status_code=401,
                    content={"error": "Invalid API key."},
                )
            # Set the user ID in contextvars for MCP tool handlers
            token = current_user_id.set(user.id)
            try:
                response = await call_next(request)
                return response
            finally:
                current_user_id.reset(token)
        except Exception as e:
            api_logger.error(f"MCP auth error: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"error": "Internal server error during authentication."},
            )
        finally:
            db.close()


def create_mcp_app() -> Starlette:
    """Create the MCP ASGI app wrapped with API key auth middleware."""
    # Get the Streamable HTTP transport ASGI app from FastMCP
    mcp_transport = mcp_server.streamable_http_app()

    # Wrap it with our auth middleware
    app = Starlette(
        middleware=[Middleware(McpApiKeyAuthMiddleware)],
    )

    # Mount the MCP transport at root of this sub-app
    app.mount("/", mcp_transport)

    return app
