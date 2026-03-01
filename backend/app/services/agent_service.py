"""Conversational video library agent using OpenAI Responses API with tool use."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from openai import AsyncOpenAI
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, extract

from app.config import settings
from app.logger import api_logger
from app.models.video import Video
from app.models.category import Category
from app.models.tag import Tag
from app.redis_client import get_redis
from app.services.embedding_service import EmbeddingService

# Maximum tool call iterations per turn to prevent runaway loops
MAX_TOOL_ITERATIONS = 10

# Tool definitions for the OpenAI Responses API
AGENT_TOOLS = [
    {
        "type": "function",
        "name": "search_videos",
        "description": "Search the user's video library using semantic similarity. Use this to find videos about a specific topic.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default 10)",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
    {
        "type": "function",
        "name": "filter_videos",
        "description": "Filter videos by categories, tags, date range, or duration. Returns matching videos with metadata.",
        "parameters": {
            "type": "object",
            "properties": {
                "categories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Category names to filter by",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tag names to filter by",
                },
                "date_from": {
                    "type": "string",
                    "description": "Start date (YYYY-MM-DD) for liked_at filter",
                },
                "date_to": {
                    "type": "string",
                    "description": "End date (YYYY-MM-DD) for liked_at filter",
                },
                "min_duration_minutes": {
                    "type": "integer",
                    "description": "Minimum video duration in minutes",
                },
                "max_duration_minutes": {
                    "type": "integer",
                    "description": "Maximum video duration in minutes",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results (default 20)",
                    "default": 20,
                },
            },
        },
    },
    {
        "type": "function",
        "name": "get_video_stats",
        "description": "Get statistics about the user's video library. Useful for answering questions about viewing habits.",
        "parameters": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "enum": [
                        "overview",
                        "top_categories",
                        "top_tags",
                        "top_channels",
                        "duration_distribution",
                    ],
                    "description": "Type of statistic to retrieve",
                }
            },
            "required": ["metric"],
        },
    },
    {
        "type": "function",
        "name": "create_playlist",
        "description": "Create a playlist on YouTube from a list of video IDs. Use this when the user asks to create a playlist.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Playlist title",
                },
                "description": {
                    "type": "string",
                    "description": "Playlist description",
                },
                "video_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of video IDs (internal DB IDs) to add",
                },
            },
            "required": ["title", "video_ids"],
        },
    },
    {
        "type": "function",
        "name": "get_temporal_trends",
        "description": "Get temporal trends of the user's video likes. Shows how interests changed over time.",
        "parameters": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["monthly", "quarterly", "yearly"],
                    "description": "Time period granularity",
                    "default": "monthly",
                }
            },
        },
    },
]


class AgentService:
    """Conversational agent that can search, analyze, and act on the video library."""

    def __init__(self, user_id: int, db: Session):
        self.user_id = user_id
        self.db = db
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.embedding_service = EmbeddingService()
        self.redis = get_redis()

    def _get_system_prompt(self) -> str:
        """Build system prompt with user's library summary for grounding."""
        total_videos = (
            self.db.query(func.count(Video.id))
            .filter(Video.user_id == self.user_id)
            .scalar()
            or 0
        )
        total_categories = (
            self.db.query(func.count(distinct(Category.id)))
            .join(Video.categories)
            .filter(Video.user_id == self.user_id)
            .scalar()
            or 0
        )
        total_channels = (
            self.db.query(func.count(distinct(Video.channel_id)))
            .filter(Video.user_id == self.user_id, Video.channel_id.isnot(None))
            .scalar()
            or 0
        )
        date_range = (
            self.db.query(func.min(Video.liked_at), func.max(Video.liked_at))
            .filter(Video.user_id == self.user_id, Video.liked_at.isnot(None))
            .first()
        )

        date_info = ""
        if date_range and date_range[0] and date_range[1]:
            date_info = f"Date range: {date_range[0].strftime('%b %Y')} to {date_range[1].strftime('%b %Y')}"

        return f"""You are a helpful assistant for the user's YouTube video library. You can search, filter, analyze, and create playlists from their liked videos.

Library summary: {total_videos} videos across {total_categories} categories from {total_channels} channels. {date_info}

Guidelines:
- Use the available tools to answer questions about their library
- When showing search results, include video titles, channels, and why they match
- When creating playlists, confirm the selection with the user first
- Be concise but informative
- If a query is ambiguous, ask for clarification
- Reference specific videos by their titles when possible"""

    def _get_session_key(self, session_id: str) -> str:
        return f"chat:{self.user_id}:{session_id}"

    def _get_previous_response_id(self, session_id: str) -> str | None:
        """Get the previous response ID for conversation continuity."""
        key = self._get_session_key(session_id)
        data = self.redis.get(key)
        if data:
            session_data = json.loads(data)
            return session_data.get("previous_response_id")
        return None

    def _save_session(
        self, session_id: str, response_id: str, message_count: int
    ) -> None:
        """Save session state to Redis."""
        key = self._get_session_key(session_id)
        now = datetime.now(timezone.utc).isoformat()

        # Get existing data or create new
        existing = self.redis.get(key)
        if existing:
            session_data = json.loads(existing)
            session_data["previous_response_id"] = response_id
            session_data["last_message_at"] = now
            session_data["message_count"] = session_data.get("message_count", 0) + 1
        else:
            session_data = {
                "session_id": session_id,
                "previous_response_id": response_id,
                "created_at": now,
                "last_message_at": now,
                "message_count": message_count,
            }

        self.redis.set(key, json.dumps(session_data), expire=3600)  # 1h TTL

    async def _execute_tool(self, tool_name: str, arguments: dict) -> Any:
        """Execute a tool call and return the result."""
        try:
            if tool_name == "search_videos":
                return await self._tool_search_videos(**arguments)
            elif tool_name == "filter_videos":
                return await self._tool_filter_videos(**arguments)
            elif tool_name == "get_video_stats":
                return self._tool_get_video_stats(**arguments)
            elif tool_name == "create_playlist":
                return await self._tool_create_playlist(**arguments)
            elif tool_name == "get_temporal_trends":
                return self._tool_get_temporal_trends(**arguments)
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            api_logger.error(f"Tool execution error ({tool_name}): {e}", exc_info=True)
            return {"error": str(e)}

    async def _tool_search_videos(self, query: str, limit: int = 10) -> list[dict]:
        """Search videos using semantic similarity."""
        results = await self.embedding_service.search_similar_videos(
            db=self.db,
            query=query,
            user_id=self.user_id,
            limit=limit,
            similarity_threshold=0.2,
        )
        # Return simplified results for the LLM
        return [
            {
                "id": v["id"],
                "title": v["title"],
                "channel": v.get("channel_title", "Unknown"),
                "duration_minutes": round((v.get("duration_seconds") or 0) / 60, 1),
                "categories": [c["name"] for c in v.get("categories", [])],
                "tags": [t["name"] for t in v.get("tags", [])],
                "similarity": v.get("similarity", 0),
                "liked_at": str(v.get("liked_at", "")),
            }
            for v in results
        ]

    async def _tool_filter_videos(
        self,
        categories: list[str] | None = None,
        tags: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        min_duration_minutes: int | None = None,
        max_duration_minutes: int | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Filter videos by various criteria."""
        query = self.db.query(Video).filter(Video.user_id == self.user_id)

        if categories:
            query = query.join(Video.categories).filter(
                func.lower(Category.name).in_([c.lower() for c in categories])
            )

        if tags:
            query = query.join(Video.tags).filter(
                func.lower(Tag.name).in_([t.lower() for t in tags])
            )

        if date_from:
            try:
                dt = datetime.strptime(date_from, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
                query = query.filter(Video.liked_at >= dt)
            except ValueError:
                pass

        if date_to:
            try:
                dt = datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                query = query.filter(Video.liked_at <= dt)
            except ValueError:
                pass

        if min_duration_minutes is not None:
            query = query.filter(Video.duration_seconds >= min_duration_minutes * 60)

        if max_duration_minutes is not None:
            query = query.filter(Video.duration_seconds <= max_duration_minutes * 60)

        videos = query.order_by(Video.liked_at.desc()).limit(limit).all()

        return [
            {
                "id": v.id,
                "title": v.title,
                "channel": v.channel_title or "Unknown",
                "duration_minutes": round((v.duration_seconds or 0) / 60, 1),
                "categories": [c.name for c in v.categories],
                "tags": [t.name for t in v.tags],
                "liked_at": str(v.liked_at) if v.liked_at else None,
            }
            for v in videos
        ]

    def _tool_get_video_stats(self, metric: str) -> dict:
        """Get library statistics."""
        if metric == "overview":
            total = (
                self.db.query(func.count(Video.id))
                .filter(Video.user_id == self.user_id)
                .scalar()
                or 0
            )
            categorized = (
                self.db.query(func.count(Video.id))
                .filter(Video.user_id == self.user_id, Video.is_categorized.is_(True))
                .scalar()
                or 0
            )
            channels = (
                self.db.query(func.count(distinct(Video.channel_id)))
                .filter(Video.user_id == self.user_id)
                .scalar()
                or 0
            )
            total_duration = (
                self.db.query(func.sum(Video.duration_seconds))
                .filter(Video.user_id == self.user_id)
                .scalar()
                or 0
            )
            return {
                "total_videos": total,
                "categorized": categorized,
                "unique_channels": channels,
                "total_watch_hours": round(total_duration / 3600, 1),
            }

        elif metric == "top_categories":
            rows = (
                self.db.query(Category.name, func.count(Video.id).label("count"))
                .join(Video.categories)
                .filter(Video.user_id == self.user_id)
                .group_by(Category.name)
                .order_by(func.count(Video.id).desc())
                .limit(10)
                .all()
            )
            return {"top_categories": [{"name": n, "count": c} for n, c in rows]}

        elif metric == "top_tags":
            rows = (
                self.db.query(Tag.name, func.count(Video.id).label("count"))
                .join(Video.tags)
                .filter(Video.user_id == self.user_id)
                .group_by(Tag.name)
                .order_by(func.count(Video.id).desc())
                .limit(15)
                .all()
            )
            return {"top_tags": [{"name": n, "count": c} for n, c in rows]}

        elif metric == "top_channels":
            rows = (
                self.db.query(Video.channel_title, func.count(Video.id).label("count"))
                .filter(
                    Video.user_id == self.user_id,
                    Video.channel_title.isnot(None),
                )
                .group_by(Video.channel_title)
                .order_by(func.count(Video.id).desc())
                .limit(10)
                .all()
            )
            return {"top_channels": [{"name": n, "count": c} for n, c in rows]}

        elif metric == "duration_distribution":
            from sqlalchemy import case, literal

            duration_case = case(
                (Video.duration_seconds < 300, literal("short (<5min)")),
                (Video.duration_seconds < 1200, literal("medium (5-20min)")),
                (Video.duration_seconds < 3600, literal("long (20-60min)")),
                else_=literal("very long (>1hr)"),
            )
            rows = (
                self.db.query(
                    duration_case.label("bucket"),
                    func.count(Video.id).label("count"),
                )
                .filter(
                    Video.user_id == self.user_id,
                    Video.duration_seconds.isnot(None),
                )
                .group_by(duration_case)
                .all()
            )
            return {
                "duration_distribution": [{"bucket": b, "count": c} for b, c in rows]
            }

        return {"error": f"Unknown metric: {metric}"}

    async def _tool_create_playlist(
        self,
        title: str,
        video_ids: list[int],
        description: str = "",
    ) -> dict:
        """Create a YouTube playlist from video IDs."""
        from app.models.user import User
        from app.models.playlist import Playlist
        from app.services.youtube_service import YouTubeService

        user = self.db.query(User).filter(User.id == self.user_id).first()
        if not user:
            return {"error": "User not found"}

        # Fetch videos
        videos = (
            self.db.query(Video)
            .filter(Video.id.in_(video_ids), Video.user_id == self.user_id)
            .all()
        )

        if not videos:
            return {"error": "No valid videos found"}

        youtube_service = YouTubeService(user)
        yt_playlist = youtube_service.create_playlist(
            title=title,
            description=description,
            privacy_status="private",
        )

        if not yt_playlist:
            return {"error": "Failed to create playlist on YouTube"}

        youtube_ids = [v.youtube_id for v in videos]
        add_result = youtube_service.add_videos_to_playlist(
            playlist_id=yt_playlist["id"],
            video_ids=youtube_ids[:250],
            position_offset=0,
        )

        # Save to DB
        db_playlist = Playlist(
            user_id=self.user_id,
            youtube_id=yt_playlist["id"],
            title=title,
            description=description,
            video_count=len(videos),
            published_at=datetime.now(timezone.utc),
            last_synced_at=datetime.now(timezone.utc),
        )
        self.db.add(db_playlist)
        self.db.commit()

        return {
            "success": True,
            "title": title,
            "video_count": len(videos),
            "added": add_result.get("succeeded", 0),
            "youtube_playlist_id": yt_playlist["id"],
        }

    def _tool_get_temporal_trends(self, period: str = "monthly") -> dict:
        """Get temporal trends of video likes."""
        if period == "monthly":
            fmt = "YYYY-MM"
        elif period == "quarterly":
            fmt = "YYYY-Q"
        else:
            fmt = "YYYY"

        # For quarterly we need special handling
        if period == "quarterly":
            rows = (
                self.db.query(
                    extract("year", Video.liked_at).label("year"),
                    func.ceil(extract("month", Video.liked_at) / 3).label("quarter"),
                    func.count(Video.id).label("count"),
                )
                .filter(Video.user_id == self.user_id, Video.liked_at.isnot(None))
                .group_by(
                    extract("year", Video.liked_at),
                    func.ceil(extract("month", Video.liked_at) / 3),
                )
                .order_by(
                    extract("year", Video.liked_at),
                    func.ceil(extract("month", Video.liked_at) / 3),
                )
                .all()
            )
            return {
                "trends": [
                    {"period": f"{int(y)}-Q{int(q)}", "count": c} for y, q, c in rows
                ]
            }
        else:
            rows = (
                self.db.query(
                    func.to_char(Video.liked_at, fmt).label("period"),
                    func.count(Video.id).label("count"),
                )
                .filter(Video.user_id == self.user_id, Video.liked_at.isnot(None))
                .group_by(func.to_char(Video.liked_at, fmt))
                .order_by(func.to_char(Video.liked_at, fmt))
                .all()
            )
            return {"trends": [{"period": p, "count": c} for p, c in rows]}

    async def chat(self, session_id: str, message: str) -> AsyncGenerator[str, None]:
        """
        Process a chat message through the agentic loop.

        Yields SSE-formatted strings for streaming to the client.
        """
        previous_response_id = self._get_previous_response_id(session_id)
        system_prompt = self._get_system_prompt()

        # Build input
        input_messages = [{"role": "user", "content": message}]

        try:
            # Initial call
            response = await self.client.responses.create(
                model=settings.openai_model,
                instructions=system_prompt,
                input=input_messages,
                tools=AGENT_TOOLS,
                previous_response_id=previous_response_id,
                stream=False,
            )

            iterations = 0

            while iterations < MAX_TOOL_ITERATIONS:
                iterations += 1

                # Check if the response has tool calls
                function_calls = [
                    item for item in response.output if item.type == "function_call"
                ]

                if not function_calls:
                    # No tool calls — extract text output
                    break

                # Execute tool calls and build function call outputs
                tool_outputs = []
                for fc in function_calls:
                    tool_name = fc.name
                    arguments = json.loads(fc.arguments)

                    # Yield progress event
                    yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name, 'arguments': arguments})}\n\n"

                    result = await self._execute_tool(tool_name, arguments)

                    tool_outputs.append(
                        {
                            "type": "function_call_output",
                            "call_id": fc.call_id,
                            "output": json.dumps(result, default=str),
                        }
                    )

                    # Yield tool result
                    yield f"data: {json.dumps({'type': 'tool_result', 'tool': tool_name, 'result': result})}\n\n"

                # Continue the conversation with tool outputs
                response = await self.client.responses.create(
                    model=settings.openai_model,
                    previous_response_id=response.id,
                    input=tool_outputs,
                    tools=AGENT_TOOLS,
                    stream=False,
                )

            # Extract final text from response
            text_parts = []
            for item in response.output:
                if item.type == "message":
                    for content in item.content:
                        if content.type == "output_text":
                            text_parts.append(content.text)

            final_text = "\n".join(text_parts)

            # Save conversation state
            self._save_session(session_id, response.id, 1)

            # Yield final message
            yield f"data: {json.dumps({'type': 'message', 'content': final_text})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            api_logger.error(f"Agent chat error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': f'An error occurred: {str(e)}'})}\n\n"
            yield "data: [DONE]\n\n"
