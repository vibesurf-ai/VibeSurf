"""
YouTube API client module for VibeSurf

This module provides a browser-session based YouTube API client that can:
- Search for videos, channels, and playlists
- Get detailed video information
- Fetch video comments
- Get channel information and videos
- Access trending videos

The client uses browser session authentication to avoid needing API keys.
"""

from .client import YouTubeApiClient
from .helpers import (
    SearchType, SortType, Duration, UploadDate,
    extract_video_id_from_url, extract_channel_id_from_url,
    extract_playlist_id_from_url, parse_youtube_duration,
    format_view_count, process_youtube_text,
    YouTubeError, NetworkError, DataExtractionError,
    AuthenticationError, RateLimitError, ContentNotFoundError
)

__all__ = [
    'YouTubeApiClient',
    'SearchType', 'SortType', 'Duration', 'UploadDate',
    'extract_video_id_from_url', 'extract_channel_id_from_url',
    'extract_playlist_id_from_url', 'parse_youtube_duration',
    'format_view_count', 'process_youtube_text',
    'YouTubeError', 'NetworkError', 'DataExtractionError',
    'AuthenticationError', 'RateLimitError', 'ContentNotFoundError'
]