"""YouTube API service for fetching liked videos and playlists."""

from datetime import datetime, timedelta
from typing import List, Dict, Any
import isodate

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.config import settings
from app.logger import api_logger
from app.models.user import User
from app.models.video import Video
from app.models.playlist import Playlist, PlaylistVideo


class YouTubeService:
    """Service for interacting with YouTube Data API v3."""

    def __init__(self, user: User):
        """Initialize YouTube service with user credentials."""
        self.user = user
        self.youtube = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize YouTube API client with user's OAuth credentials."""
        if not self.user.access_token:
            raise ValueError("User has no access token")

        # Create credentials object
        creds = Credentials(
            token=self.user.access_token,
            refresh_token=self.user.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.youtube_client_id,
            client_secret=settings.youtube_client_secret,
            scopes=settings.youtube_scopes,
        )

        # Check if token is expired and refresh if needed
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Update user's tokens in database (will be done by caller)
            self.user.access_token = creds.token
            self.user.token_expires_at = datetime.utcnow() + timedelta(
                seconds=creds.expiry.timestamp() - datetime.utcnow().timestamp()
            )

        self.youtube = build("youtube", "v3", credentials=creds)

    def fetch_liked_videos(
        self, db: Session, max_results: int = 50
    ) -> tuple[List[Video], int]:
        """
        Fetch user's liked videos from YouTube.

        Args:
            db: Database session
            max_results: Maximum number of videos to fetch

        Returns:
            Tuple of (list of Video objects, total count)
        """
        try:
            videos = []
            next_page_token = None
            total_fetched = 0

            while total_fetched < max_results:
                # Request liked videos
                request = self.youtube.videos().list(
                    part="snippet,contentDetails,statistics",
                    myRating="like",
                    maxResults=min(50, max_results - total_fetched),
                    pageToken=next_page_token,
                )

                response = request.execute()

                # Process each video
                for item in response.get("items", []):
                    video = self._process_video_item(db, item)
                    if video:
                        videos.append(video)

                total_fetched += len(response.get("items", []))
                next_page_token = response.get("nextPageToken")

                if not next_page_token:
                    break

            return videos, total_fetched

        except HttpError as e:
            api_logger.error(f"YouTube API error: {e}")
            raise

    def fetch_liked_videos_paginated(
        self, db: Session, page_token: str | None = None, max_results: int = 50
    ) -> tuple[List[Video], str | None]:
        """
        Fetch a single page of liked videos from YouTube.

        Args:
            db: Database session
            page_token: Token for the next page (None for first page)
            max_results: Maximum number of videos to fetch in this page

        Returns:
            Tuple of (list of Video objects, next page token or None)
        """
        try:
            # Request liked videos
            request = self.youtube.videos().list(
                part="snippet,contentDetails,statistics",
                myRating="like",
                maxResults=min(50, max_results),
                pageToken=page_token,
            )

            response = request.execute()

            # Process each video
            videos = []
            for item in response.get("items", []):
                video = self._process_video_item(db, item)
                if video:
                    videos.append(video)

            next_page_token = response.get("nextPageToken")
            return videos, next_page_token

        except HttpError as e:
            api_logger.error(f"YouTube API error: {e}")
            raise

    def fetch_user_playlists(
        self, db: Session, max_results: int = 50
    ) -> tuple[List[Playlist], int]:
        """
        Fetch user's playlists from YouTube.

        Args:
            db: Database session
            max_results: Maximum number of playlists to fetch

        Returns:
            Tuple of (list of Playlist objects, total count)
        """
        try:
            playlists = []
            next_page_token = None
            total_fetched = 0

            while total_fetched < max_results:
                request = self.youtube.playlists().list(
                    part="snippet,contentDetails",
                    mine=True,
                    maxResults=min(50, max_results - total_fetched),
                    pageToken=next_page_token,
                )

                response = request.execute()

                for item in response.get("items", []):
                    playlist = self._process_playlist_item(db, item)
                    if playlist:
                        playlists.append(playlist)

                total_fetched += len(response.get("items", []))
                next_page_token = response.get("nextPageToken")

                if not next_page_token:
                    break

            return playlists, total_fetched

        except HttpError as e:
            api_logger.error(f"YouTube API error: {e}")
            raise

    def fetch_playlist_videos(
        self, db: Session, playlist: Playlist, max_results: int = 50
    ) -> List[Video]:
        """
        Fetch videos from a specific playlist.

        Args:
            db: Database session
            playlist: Playlist object
            max_results: Maximum number of videos to fetch

        Returns:
            List of Video objects
        """
        try:
            videos = []
            next_page_token = None
            position = 0

            while len(videos) < max_results:
                request = self.youtube.playlistItems().list(
                    part="snippet,contentDetails",
                    playlistId=playlist.youtube_id,
                    maxResults=min(50, max_results - len(videos)),
                    pageToken=next_page_token,
                )

                response = request.execute()

                # Get video IDs for batch details request
                video_ids = [
                    item["contentDetails"]["videoId"]
                    for item in response.get("items", [])
                ]

                if video_ids:
                    # Fetch full video details
                    videos_response = (
                        self.youtube.videos()
                        .list(
                            part="snippet,contentDetails,statistics",
                            id=",".join(video_ids),
                        )
                        .execute()
                    )

                    for video_item in videos_response.get("items", []):
                        video = self._process_video_item(db, video_item)
                        if video:
                            # Create playlist-video association
                            playlist_video = (
                                db.query(PlaylistVideo)
                                .filter_by(playlist_id=playlist.id, video_id=video.id)
                                .first()
                            )

                            if not playlist_video:
                                playlist_video = PlaylistVideo(
                                    playlist_id=playlist.id,
                                    video_id=video.id,
                                    position=position,
                                )
                                db.add(playlist_video)

                            videos.append(video)
                            position += 1

                next_page_token = response.get("nextPageToken")
                if not next_page_token:
                    break

            db.commit()
            return videos

        except HttpError as e:
            api_logger.error(f"YouTube API error: {e}")
            raise

    def _process_video_item(self, db: Session, item: Dict[str, Any]) -> Video | None:
        """Process a video item from YouTube API response."""
        try:
            youtube_id = item["id"]
            snippet = item.get("snippet", {})
            content_details = item.get("contentDetails", {})
            statistics = item.get("statistics", {})

            # Parse duration
            duration_seconds = None
            if content_details.get("duration"):
                duration = isodate.parse_duration(content_details["duration"])
                duration_seconds = int(duration.total_seconds())

            # Check if video already exists
            video = (
                db.query(Video)
                .filter_by(user_id=self.user.id, youtube_id=youtube_id)
                .first()
            )

            if not video:
                video = Video(
                    user_id=self.user.id,
                    youtube_id=youtube_id,
                    title=snippet.get("title", ""),
                    description=snippet.get("description"),
                    thumbnail_url=snippet.get("thumbnails", {})
                    .get("high", {})
                    .get("url"),
                    channel_title=snippet.get("channelTitle"),
                    channel_id=snippet.get("channelId"),
                    duration_seconds=duration_seconds,
                    published_at=(
                        datetime.fromisoformat(
                            snippet.get("publishedAt").replace("Z", "+00:00")
                        )
                        if snippet.get("publishedAt")
                        else None
                    ),
                    view_count=int(statistics.get("viewCount", 0)),
                    like_count=int(statistics.get("likeCount", 0)),
                    liked_at=datetime.utcnow(),
                )
                db.add(video)
            else:
                # Update existing video
                video.title = snippet.get("title", video.title)
                video.description = snippet.get("description", video.description)
                video.view_count = int(statistics.get("viewCount", 0))
                video.like_count = int(statistics.get("likeCount", 0))

            db.commit()
            db.refresh(video)
            return video

        except Exception as e:
            api_logger.error(f"Error processing video item: {e}")
            return None

    def _process_playlist_item(
        self, db: Session, item: Dict[str, Any]
    ) -> Playlist | None:
        """Process a playlist item from YouTube API response."""
        try:
            youtube_id = item["id"]
            snippet = item.get("snippet", {})
            content_details = item.get("contentDetails", {})

            # Check if playlist already exists
            playlist = (
                db.query(Playlist)
                .filter_by(user_id=self.user.id, youtube_id=youtube_id)
                .first()
            )

            if not playlist:
                playlist = Playlist(
                    user_id=self.user.id,
                    youtube_id=youtube_id,
                    title=snippet.get("title", ""),
                    description=snippet.get("description"),
                    thumbnail_url=snippet.get("thumbnails", {})
                    .get("high", {})
                    .get("url"),
                    channel_title=snippet.get("channelTitle"),
                    channel_id=snippet.get("channelId"),
                    video_count=content_details.get("itemCount", 0),
                    published_at=(
                        datetime.fromisoformat(
                            snippet.get("publishedAt").replace("Z", "+00:00")
                        )
                        if snippet.get("publishedAt")
                        else None
                    ),
                )
                db.add(playlist)
            else:
                # Update existing playlist
                playlist.title = snippet.get("title", playlist.title)
                playlist.description = snippet.get("description", playlist.description)
                playlist.video_count = content_details.get("itemCount", 0)
                playlist.last_synced_at = datetime.utcnow()

            db.commit()
            db.refresh(playlist)
            return playlist

        except Exception as e:
            api_logger.error(f"Error processing playlist item: {e}")
            return None

    def get_user_info(self) -> Dict[str, Any] | None:
        """Fetch user's basic information from YouTube."""
        try:
            request = self.youtube.channels().list(part="snippet", mine=True)
            response = request.execute()

            if response.get("items"):
                item = response["items"][0]
                # Return both id and snippet data
                return {
                    "id": item.get("id"),
                    **item.get("snippet", {}),
                }

            return None

        except HttpError as e:
            api_logger.error(f"YouTube API error: {e}")
            return None

    def create_playlist(
        self, title: str, description: str | None = None, privacy_status: str = "private"
    ) -> Dict[str, Any] | None:
        """
        Create a new YouTube playlist.

        Args:
            title: Playlist title (required)
            description: Playlist description (optional)
            privacy_status: "private", "unlisted", or "public" (default: "private")

        Returns:
            Playlist details from YouTube API or None if failed

        Raises:
            HttpError: If YouTube API request fails
        """
        try:
            request_body = {
                "snippet": {
                    "title": title,
                    "description": description or "",
                },
                "status": {
                    "privacyStatus": privacy_status,
                },
            }

            request = self.youtube.playlists().insert(
                part="snippet,status", body=request_body
            )

            response = request.execute()
            api_logger.info(f"Created playlist: {title} (ID: {response.get('id')})")
            return response

        except HttpError as e:
            api_logger.error(f"Failed to create playlist '{title}': {e}")
            raise

    def add_videos_to_playlist(
        self, playlist_id: str, video_ids: List[str], position_offset: int = 0
    ) -> Dict[str, Any]:
        """
        Add videos to a YouTube playlist in batch.

        Args:
            playlist_id: YouTube playlist ID
            video_ids: List of YouTube video IDs to add
            position_offset: Starting position in playlist (default: 0)

        Returns:
            Dict with success/failure counts and details:
            {
                "total": 10,
                "succeeded": 8,
                "failed": 2,
                "failures": [{"video_id": "xyz", "error": "..."}]
            }

        Note: Each video addition costs 50 quota units
        """
        results = {"total": len(video_ids), "succeeded": 0, "failed": 0, "failures": []}

        for i, video_id in enumerate(video_ids):
            try:
                request_body = {
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": video_id},
                        "position": position_offset + i,
                    }
                }

                self.youtube.playlistItems().insert(
                    part="snippet", body=request_body
                ).execute()

                results["succeeded"] += 1
                api_logger.debug(
                    f"Added video {video_id} to playlist {playlist_id} at position {position_offset + i}"
                )

            except HttpError as e:
                results["failed"] += 1
                error_msg = str(e)
                results["failures"].append({"video_id": video_id, "error": error_msg})
                api_logger.warning(
                    f"Failed to add video {video_id} to playlist {playlist_id}: {e}"
                )

        api_logger.info(
            f"Added {results['succeeded']}/{results['total']} videos to playlist {playlist_id}"
        )
        return results
