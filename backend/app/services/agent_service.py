"""Conversational video library agent using OpenAI Responses API with tool use."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Literal

from openai.types.shared_params import Reasoning
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, extract

from app.config import settings
from app.logger import api_logger
from app.observability import AsyncOpenAI, tool_span, trace_span
from app.models.video import Video
from app.models.category import Category
from app.models.tag import Tag
from app.models.chat import ChatSession
from app.models.user import User
from app.redis_client import get_redis
from app.services.embedding_service import EmbeddingService
from app.schemas.chat import ChatStreamEvent

# Maximum tool call iterations per turn to prevent runaway loops
MAX_TOOL_ITERATIONS = 10

# System prompt cache TTL in seconds (5 minutes)
SYSTEM_PROMPT_CACHE_TTL = 300

# Tool result cache TTL in seconds (5 minutes)
TOOL_RESULT_CACHE_TTL = 300

# Optimization C: patterns that indicate a simple, low-reasoning query
_SIMPLE_QUERY_PATTERNS = [
    re.compile(r"\b(how many|count|total|number of)\b", re.IGNORECASE),
    re.compile(
        r"\b(what are my|list|show me all)\b.{0,30}\b(categories|tags|channels)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(stats|statistics|overview)\b", re.IGNORECASE),
]

# Optimization D: token budgets per turn type
_INTERMEDIATE_MAX_TOKENS = 1024  # tool-selection turns (short JSON output)
_FINAL_MAX_TOKENS = settings.openai_max_tokens  # synthesis turn (full response)

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
        "description": "Filter videos by categories, tags, date range, or duration. Results are always sorted by most recently liked first — call with just a limit to list the user's most recent liked videos. Returns matching videos with metadata.",
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


def format_data_freshness(
    last_sync_at: datetime | None, latest_liked_at: datetime | None
) -> str:
    """Build the data-freshness section of the agent system prompt.

    The agent only sees videos that have been synced into the database;
    likes newer than the last sync are invisible to every tool. Making the
    cutoff explicit lets the agent caveat recency answers instead of
    asserting a false negative ("you have no recent food videos") when the
    library is simply out of date.
    """
    if not last_sync_at and not latest_liked_at:
        return (
            "Data freshness: the library has never been synced from YouTube, "
            "so it is empty or stale. Tell the user to sync from the dashboard."
        )
    parts = []
    if latest_liked_at:
        parts.append(
            "the most recent liked video in the library is from "
            f"{latest_liked_at.strftime('%Y-%m-%d')}"
        )
    if last_sync_at:
        parts.append(
            "the library was last synced from YouTube on "
            f"{last_sync_at.strftime('%Y-%m-%d')}"
        )
    return (
        "Data freshness: "
        + "; ".join(parts)
        + ". Videos liked after the last sync are NOT in the library and no "
        "tool can find them. If the user asks about recently liked videos "
        "and you find no matches (or the question implies likes newer than "
        "the last sync), say the library may be out of date and suggest "
        "syncing from the dashboard."
    )


def _is_simple_query(message: str) -> bool:
    """Return True if the message matches known low-complexity patterns (Optimization C)."""
    return any(p.search(message) for p in _SIMPLE_QUERY_PATTERNS)


def _min_reasoning_effort(model: str) -> Literal["none", "minimal", "low"]:
    """Lowest reasoning effort the given model accepts (for simple queries).

    The floor tier is model-family specific and sending the wrong one is a
    hard 400 from OpenAI (this broke prod simple queries twice: gpt-4.1-mini
    rejected "minimal", then gpt-5-mini rejected "none"):
    - gpt-5.1 / gpt-5.2 / ...: "none" (renamed from "minimal", which they reject)
    - gpt-5, gpt-5-mini, gpt-5-nano: "minimal" ("none" not supported)
    - anything else: "low" — accepted by every reasoning-capable model.
    """
    if re.match(r"gpt-5\.\d", model):
        return "none"
    if model == "gpt-5" or model.startswith(("gpt-5-", "gpt-5@")):
        return "minimal"
    return "low"


def _tool_cache_key(user_id: int, tool_name: str, arguments: dict) -> str:
    """Build a stable Redis cache key for a tool call (Optimization B)."""
    params_hash = hashlib.sha256(
        json.dumps(arguments, sort_keys=True).encode()
    ).hexdigest()[:16]
    return f"tool_result:{user_id}:{tool_name}:{params_hash}"


class AgentService:
    """Conversational agent that can search, analyze, and act on the video library."""

    def __init__(self, user_id: int, db: Session):
        self.user_id = user_id
        self.db = db
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.embedding_service = EmbeddingService()
        self._redis = get_redis()

    async def _get_system_prompt(self) -> str:
        """Build system prompt with user's library summary for grounding.

        Result is cached in Redis for SYSTEM_PROMPT_CACHE_TTL seconds to avoid
        4 DB round-trips on every message (Optimization A).
        """
        cache_key = f"chat_context:{self.user_id}"
        cached = self._redis.get(cache_key)
        if cached:
            api_logger.debug(f"System prompt cache hit for user {self.user_id}")
            return cached

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

        user = self.db.query(User).filter(User.id == self.user_id).first()
        freshness = format_data_freshness(
            last_sync_at=user.last_sync_at if user else None,
            latest_liked_at=date_range[1] if date_range else None,
        )

        prompt = f"""You are a helpful assistant for the user's YouTube video library. You can search, filter, analyze, and create playlists from their liked videos.

Library summary: {total_videos} videos across {total_categories} categories from {total_channels} channels. {date_info}

{freshness}

Guidelines:
- Use the available tools to answer questions about their library
- For questions about the most recent / latest liked videos, use filter_videos with just a limit — its results are sorted by most recently liked first. Never use search_videos for recency questions: it ranks by topic similarity, not by when the video was liked
- When showing search results, include video titles, channels, and why they match
- When creating playlists, confirm the selection with the user first
- Be concise but informative
- If a query is ambiguous, ask for clarification
- Reference specific videos by their titles when possible"""

        self._redis.set(cache_key, prompt, expire=SYSTEM_PROMPT_CACHE_TTL)
        return prompt

    def _get_previous_response_id(self, session_id: str) -> str | None:
        """Get the previous response ID for conversation continuity."""
        session = (
            self.db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == self.user_id)
            .first()
        )
        return session.previous_response_id if session else None

    def _save_session(
        self, session_id: str, response_id: str, _message_count: int
    ) -> None:
        """Save response continuity state to DB session metadata."""
        session = (
            self.db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == self.user_id)
            .first()
        )
        if not session:
            return

        session.previous_response_id = response_id
        session.last_message_at = datetime.now(timezone.utc)
        self.db.commit()

    async def _execute_tool(self, tool_name: str, arguments: dict) -> Any:
        """Execute a tool call and return the result.

        Read-only tools are cached in Redis by (user_id, tool_name, params_hash)
        with a 5-minute TTL (Optimization B). The create_playlist tool is never
        cached because it performs writes.
        """
        with tool_span(tool_name, input=arguments) as span:
            result, cache_hit = await self._execute_tool_inner(tool_name, arguments)
            span.update(
                output=result,
                metadata={"cache_hit": cache_hit, "user_id": self.user_id},
            )
            return result

    async def _execute_tool_inner(
        self, tool_name: str, arguments: dict
    ) -> tuple[Any, bool]:
        """Original tool dispatch; returns (result, served_from_cache)."""
        # Skip caching for write tools
        cacheable = tool_name != "create_playlist"

        if cacheable:
            cache_key = _tool_cache_key(self.user_id, tool_name, arguments)
            cached_raw = self._redis.get(cache_key)
            if cached_raw:
                api_logger.debug(f"Tool cache hit: {tool_name}")
                return json.loads(cached_raw), True

        try:
            if tool_name == "search_videos":
                result = await self._tool_search_videos(**arguments)
            elif tool_name == "filter_videos":
                result = await self._tool_filter_videos(**arguments)
            elif tool_name == "get_video_stats":
                result = self._tool_get_video_stats(**arguments)
            elif tool_name == "create_playlist":
                result = await self._tool_create_playlist(**arguments)
            elif tool_name == "get_temporal_trends":
                result = self._tool_get_temporal_trends(**arguments)
            else:
                return {"error": f"Unknown tool: {tool_name}"}, False
        except Exception as e:
            api_logger.error(f"Tool execution error ({tool_name}): {e}", exc_info=True)
            # Roll back the aborted transaction so subsequent DB operations work.
            # Without this, a failed DB query inside a tool leaves the PostgreSQL
            # transaction in an aborted state, causing InFailedSqlTransaction on
            # every later commit (session save, assistant message persist, etc.).
            try:
                self.db.rollback()
            except Exception:
                pass
            return {
                "error": f"Tool '{tool_name}' failed. Please try a different query."
            }, False

        if cacheable:
            self._redis.set(
                cache_key,
                json.dumps(result, default=str),
                expire=TOOL_RESULT_CACHE_TTL,
            )

        return result, False

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

    async def chat(
        self, session_id: str, message: str
    ) -> AsyncGenerator[ChatStreamEvent, None]:
        """
        Process a chat message through the agentic loop.

        Yields structured events for StreamingResponse JSON Lines output.
        """
        with trace_span(
            "chat-turn",
            session_id=session_id,
            user_id=str(self.user_id),
            input=message,
            tags=["chat", "prompt:v2"],
        ) as turn_span:
            # Optimization E: fetch system prompt and previous_response_id concurrently.
            # _get_system_prompt is async (and cached); _get_previous_response_id is sync
            # so we run it in a thread to allow true parallelism.
            system_prompt, previous_response_id = await asyncio.gather(
                self._get_system_prompt(),
                asyncio.get_running_loop().run_in_executor(
                    None, self._get_previous_response_id, session_id
                ),
            )

            # Optimization C: choose reasoning effort based on query complexity.
            # The floor tier for simple lookups is model-dependent — see
            # _min_reasoning_effort.
            simple = _is_simple_query(message)
            reasoning_effort: Literal["none", "minimal", "low"] = (
                _min_reasoning_effort(settings.openai_model) if simple else "low"
            )
            api_logger.debug(
                f"Query reasoning effort: {reasoning_effort!r} (simple={simple})"
            )

            # Build input
            input_messages = [{"role": "user", "content": message}]

            try:
                # Initial call — use full token budget since we don't know yet whether
                # the model will call a tool or answer directly (Optimization D).
                response = await self.client.responses.create(
                    model=settings.openai_model,
                    instructions=system_prompt,
                    input=input_messages,
                    tools=AGENT_TOOLS,
                    previous_response_id=previous_response_id,
                    stream=False,
                    reasoning=Reasoning(effort=reasoning_effort),
                    max_output_tokens=_FINAL_MAX_TOKENS,
                )

                iterations = 0

                while iterations < MAX_TOOL_ITERATIONS:
                    iterations += 1

                    # Check if the response has tool calls
                    function_calls = [
                        item for item in response.output if item.type == "function_call"
                    ]

                    if not function_calls:
                        # No tool calls — final synthesis text is already in the response
                        break

                    # Execute tool calls and build function call outputs
                    tool_outputs = []
                    for fc in function_calls:
                        tool_name = fc.name
                        arguments = json.loads(fc.arguments)

                        # Yield progress event
                        yield ChatStreamEvent(
                            type="tool_call",
                            tool=tool_name,
                            arguments=arguments,
                        )

                        result = await self._execute_tool(tool_name, arguments)

                        tool_outputs.append(
                            {
                                "type": "function_call_output",
                                "call_id": fc.call_id,
                                "output": json.dumps(result, default=str),
                            }
                        )

                        # Yield tool result
                        yield ChatStreamEvent(
                            type="tool_result",
                            tool=tool_name,
                            result=result,
                        )

                    # Check if this is the last iteration (synthesis turn next)
                    is_final_turn = iterations >= MAX_TOOL_ITERATIONS - 1
                    next_max_tokens = (
                        _FINAL_MAX_TOKENS if is_final_turn else _INTERMEDIATE_MAX_TOKENS
                    )

                    # Continue the conversation with tool outputs
                    response = await self.client.responses.create(
                        model=settings.openai_model,
                        previous_response_id=response.id,
                        input=tool_outputs,
                        tools=AGENT_TOOLS,
                        stream=False,
                        reasoning=Reasoning(effort=reasoning_effort),
                        max_output_tokens=next_max_tokens,
                    )

                # Extract final text from response
                text_parts = []
                for item in response.output:
                    if item.type == "message":
                        for content in item.content:
                            if content.type == "output_text":
                                text_parts.append(content.text)

                final_text = "\n".join(text_parts)
                turn_span.update(output=final_text)

                # Save conversation state
                self._save_session(session_id, response.id, 1)

                # Yield final message
                yield ChatStreamEvent(type="message", content=final_text)
                yield ChatStreamEvent(type="done")

            except Exception as e:
                api_logger.error(f"Agent chat error: {e}", exc_info=True)
                # Clear any aborted transaction (e.g. a failed _save_session):
                # callers may reuse this session (the eval runner shares one
                # across cases) and would otherwise hit InFailedSqlTransaction.
                try:
                    self.db.rollback()
                except Exception:
                    pass
                yield ChatStreamEvent(
                    type="error",
                    content="Something went wrong while processing your request. Please try again.",
                )
                yield ChatStreamEvent(type="done")
