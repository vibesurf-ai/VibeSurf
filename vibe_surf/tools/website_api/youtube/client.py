import asyncio
import json
import pdb
import re
import copy
import time
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Callable, Union, Any
import httpx
from tenacity import retry, stop_after_attempt, wait_fixed
from urllib.parse import parse_qs, unquote, urlencode
from youtube_transcript_api import YouTubeTranscriptApi

from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.logger import get_logger

from .helpers import (
    SearchType, SortType, Duration, UploadDate,
    extract_cookies_from_browser, extract_video_id_from_url,
    extract_channel_id_from_url, extract_playlist_id_from_url,
    parse_youtube_duration, format_view_count, parse_youtube_time,
    process_youtube_text, validate_youtube_data, sanitize_filename,
    extract_ytcfg_data, extract_initial_data, get_desktop_user_agent,
    build_search_url, extract_continuation_token, decode_html_entities,
    extract_thumbnail_url, generate_visitor_data,
    YouTubeError, NetworkError, DataExtractionError,
    AuthenticationError, RateLimitError, ContentNotFoundError
)

logger = get_logger(__name__)


class YouTubeApiClient:
    """
    YouTube API client with integrated browser session management.
    This client handles API communication through browser session for authentication.
    """

    def __init__(self, browser_session: AgentBrowserSession, timeout: int = 60, proxy: Optional[str] = None):
        """
        Initialize the YouTube API client

        Args:
            browser_session: Browser session for authentication
            timeout: Request timeout in seconds
            proxy: Proxy URL if needed
        """
        self.browser_session = browser_session
        self.target_id = None
        self.new_tab = False
        self.proxy = proxy
        self.timeout = timeout
        self._base_url = "https://www.youtube.com"
        self._api_base = "https://www.youtube.com/youtubei/v1"

        # YouTube API key and client version (these are usually extracted from the page)
        self._api_key = None
        self._client_version = "2.20240229.01.00"
        self._visitor_data = generate_visitor_data()

        # Default headers for YouTube
        self.default_headers = {
            "User-Agent": get_desktop_user_agent(),
            "Origin": "https://www.youtube.com",
            "Referer": "https://www.youtube.com/",
            "Content-Type": "application/json;charset=UTF-8",
        }
        self.cookies = {}

    async def setup(self, target_id: Optional[str] = None):
        """
        Setup YouTube client by navigating to the site and extracting cookies

        Args:
            target_id: Specific browser target ID to use

        Raises:
            AuthenticationError: If setup fails
        """
        try:
            if self.target_id and self.cookies and self._api_key:
                logger.info("YouTube client already setup. Return!")
                return

            new_tab = False
            if target_id:
                self.target_id = target_id
            else:
                # Navigate to YouTube home page
                self.target_id = await self.browser_session.navigate_to_url(
                    "https://www.youtube.com/", new_tab=True
                )
                await asyncio.sleep(2)  # Wait for page load
                self.new_tab = True

            # Extract cookies from browser
            cdp_session = await self.browser_session.get_or_create_cdp_session(target_id=self.target_id)
            result = await asyncio.wait_for(
                cdp_session.cdp_client.send.Storage.getCookies(session_id=cdp_session.session_id),
                timeout=8.0
            )
            web_cookies = result.get('cookies', [])

            cookie_str, cookie_dict = extract_cookies_from_browser(web_cookies)
            self.default_headers["Cookie"] = cookie_str
            self.cookies = cookie_dict

            # Get user agent from browser
            user_agent_result = await cdp_session.cdp_client.send.Runtime.evaluate(
                params={
                    'expression': "navigator.userAgent",
                    'returnByValue': True,
                    'awaitPromise': True
                },
                session_id=cdp_session.session_id,
            )
            user_agent = user_agent_result.get('result', {}).get('value')
            if user_agent:
                self.default_headers["User-Agent"] = user_agent

            # Extract API key and configuration from page
            await self._extract_api_config()

            # is_logged_in = await self.check_login()
            # if not is_logged_in:
            #     self.cookies = {}
            #     del self.default_headers["Cookie"]
            #     raise AuthenticationError(f"Please login in [Youtube]({self._base_url}) first!")

            logger.info("YouTube client setup completed successfully")

        except Exception as e:
            logger.error(f"Failed to setup YouTube client: {e}")
            raise AuthenticationError(f"Setup failed: {e}")

    async def _extract_api_config(self):
        """Extract API key and configuration from YouTube page"""
        try:
            cdp_session = await self.browser_session.get_or_create_cdp_session(target_id=self.target_id)

            # Get page content to extract API key
            content_result = await cdp_session.cdp_client.send.Runtime.evaluate(
                params={
                    'expression': "document.documentElement.outerHTML",
                    'returnByValue': True,
                },
                session_id=cdp_session.session_id,
            )

            html_content = content_result.get('result', {}).get('value', '')

            # Extract API key from page
            api_key_match = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', html_content)
            if api_key_match:
                self._api_key = api_key_match.group(1)
                logger.info(f"Extracted YouTube API key: {self._api_key[:10]}...")

            # Extract client version
            version_match = re.search(r'"clientVersion":"([^"]+)"', html_content)
            if version_match:
                self._client_version = version_match.group(1)
                self.default_headers["X-YouTube-Client-Version"] = self._client_version

            # Extract visitor data if available
            visitor_match = re.search(r'"visitorData":"([^"]+)"', html_content)
            if visitor_match:
                self._visitor_data = visitor_match.group(1)

        except Exception as e:
            logger.warning(f"Failed to extract YouTube API config: {e}")
            # Use default values if extraction fails

    async def check_login(self) -> bool:
        """Check if the client is working by making a simple request"""
        try:
            logger.info("Testing YouTube client status...")

            # Try to make a simple search request
            test_response = await self.search_videos("kimi-k2-thinking")

            if test_response and len(test_response) >= 0:
                logger.info("YouTube client status: Valid")
                return True

            logger.warning("YouTube client status: Invalid response")
            return False

        except Exception as e:
            logger.error(f"Failed to check YouTube client status: {e}")
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    async def _make_request(self, method: str, url: str, **kwargs):
        """
        Make HTTP request with error handling and retry logic

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional request parameters

        Returns:
            Response data
        """
        raw_response = kwargs.pop("raw_response", False)

        async with httpx.AsyncClient(proxy=self.proxy, timeout=self.timeout) as client:
            response = await client.request(method, url, **kwargs)

        # Handle common error status codes
        if response.status_code == 403:
            raise AuthenticationError("Access forbidden - may need login or verification")
        elif response.status_code == 429:
            raise RateLimitError("Rate limit exceeded")
        elif response.status_code == 404:
            raise ContentNotFoundError("Content not found")
        elif response.status_code >= 500:
            raise NetworkError(f"Server error: {response.status_code}")

        if raw_response:
            return response

        try:
            if 'application/json' in response.headers.get('content-type', ''):
                return response.json()
            else:
                return response.text

        except json.JSONDecodeError:
            return response.text

    async def _make_api_request(self, endpoint: str, data: Dict, **kwargs) -> Dict:
        """Make YouTube Internal API request"""
        if not self._api_key:
            raise AuthenticationError("YouTube API key not available")

        url = f"{self._api_base}/{endpoint}?key={self._api_key}"

        # Add default context to request data
        request_data = {
            "context": {
                "client": {
                    "clientName": "WEB",
                    "clientVersion": self._client_version,
                    "visitorData": self._visitor_data,
                },
                "user": {
                    "lockedSafetyMode": False
                },
                "request": {
                    "useSsl": True
                }
            },
            **data
        }

        json_payload = json.dumps(request_data, separators=(",", ":"), ensure_ascii=False)

        return await self._make_request(
            "POST", url,
            data=json_payload,
            headers=self.default_headers,
            **kwargs
        )

    def _find_video_renderers(self, data: Any) -> List[Dict]:
        """
        Recursively find all videoRenderer objects in the YouTube API response

        Args:
            data: YouTube API response data (can be dict, list, or any type)
            max_results: Maximum number of video renderers to find

        Returns:
            List of videoRenderer data
        """
        video_renderers = []

        def recursive_search(obj, current_count=0):

            if isinstance(obj, dict):
                # Check if this dict contains a videoRenderer
                if "videoRenderer" in obj:
                    video_data = obj["videoRenderer"]
                    if video_data and isinstance(video_data, dict):
                        video_renderers.append(video_data)
                        current_count += 1

                # Recursively search all values in the dict
                for value in obj.values():
                    current_count = recursive_search(value, current_count)

            elif isinstance(obj, list):
                # Recursively search all items in the list
                for item in obj:
                    current_count = recursive_search(item, current_count)

            return current_count

        recursive_search(data)
        return video_renderers

    async def search_videos(
            self,
            query: str,
            max_results: int = 20,
            continuation_token: Optional[str] = None,
            sleep_time: float = 0.1
    ) -> List[Dict]:
        """
        Search YouTube videos with pagination support

        Args:
            query: Search query
            max_results: Maximum number of results to fetch (0 for all available)
            continuation_token: Token for pagination
            sleep_time: Sleep time between requests

        Returns:
            List of simplified video information
        """
        try:
            videos = []
            continuations = []

            if continuation_token:
                # Use provided continuation token
                continuations.append(continuation_token)
            else:
                # Initial search request
                data = {"query": query}
                response = await self._make_api_request("search", data)

                # Extract videos from initial response
                video_renderers = self._find_video_renderers(response)
                for video_data in video_renderers:
                    if max_results > 0 and len(videos) >= max_results:
                        break
                    video_info = self._extract_video_info(video_data)
                    if video_info:
                        videos.append(video_info)

                # Extract continuation tokens for more results
                continuation_tokens = self._extract_continuation_tokens(response)
                continuations.extend(continuation_tokens)

            # Process continuation tokens for more videos
            while continuations and (max_results == 0 or len(videos) < max_results):
                current_continuation = continuations.pop(0)

                # Make API request with continuation token
                data = {"continuation": current_continuation}
                response = await self._make_api_request("search", data)

                if not response:
                    break

                # Extract videos from continuation response
                video_renderers = self._find_video_renderers(response)
                batch_videos = []

                for video_data in video_renderers:
                    if max_results > 0 and len(videos) + len(batch_videos) >= max_results:
                        break
                    video_info = self._extract_video_info(video_data)
                    if video_info:
                        batch_videos.append(video_info)

                videos.extend(batch_videos)

                # Look for more continuation tokens
                continuation_tokens = self._extract_continuation_tokens(response)
                for token in continuation_tokens:
                    if token not in continuations:
                        continuations.append(token)

                logger.info(f"Fetched {len(batch_videos)} videos, total: {len(videos)}")

                # Sleep between requests to avoid rate limiting
                if continuations and sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            return videos[:max_results] if max_results > 0 else videos

        except Exception as e:
            logger.error(f"Failed to search videos: {e}")
            return []

    def _extract_video_info(self, video_data: Dict) -> Optional[Dict]:
        """Extract simplified video information from YouTube video data"""
        try:
            video_id = video_data.get("videoId")
            if not video_id:
                return None

            title = video_data.get("title", {}).get("runs", [{}])[0].get("text", "")
            if not title and "accessibility" in video_data.get("title", {}):
                title = video_data["title"]["accessibility"]["accessibilityData"]["label"]

            # Extract view count
            view_count_text = ""
            view_count_runs = video_data.get("viewCountText", {}).get("simpleText", "")
            if not view_count_runs:
                view_count_runs = video_data.get("shortViewCountText", {}).get("simpleText", "")
            view_count = format_view_count(view_count_runs)

            # Extract duration
            duration_text = video_data.get("lengthText", {}).get("simpleText", "")
            duration_seconds = 0
            if duration_text:
                # Convert MM:SS or HH:MM:SS to seconds
                time_parts = duration_text.split(":")
                if len(time_parts) == 2:  # MM:SS
                    duration_seconds = int(time_parts[0]) * 60 + int(time_parts[1])
                elif len(time_parts) == 3:  # HH:MM:SS
                    duration_seconds = int(time_parts[0]) * 3600 + int(time_parts[1]) * 60 + int(time_parts[2])

            # Extract channel info
            channel_data = video_data.get("longBylineText", {}).get("runs", [{}])[0]
            channel_name = channel_data.get("text", "")
            channel_url = channel_data.get("navigationEndpoint", {}).get("commandMetadata", {}).get(
                "webCommandMetadata", {}).get("url", "")
            channel_id = extract_channel_id_from_url(channel_url) if channel_url else ""

            # Extract thumbnail
            thumbnails = video_data.get("thumbnail", {}).get("thumbnails", [])
            thumbnail_url = extract_thumbnail_url(thumbnails)

            # Extract published time
            published_time_text = video_data.get("publishedTimeText", {}).get("simpleText", "")

            description = ''
            if 'descriptionSnippet' in video_data:
                for desc in video_data.get('descriptionSnippet', {}).get('runs', {}):
                    description += desc.get('text', '')

            return {
                "video_id": video_id,
                "title": process_youtube_text(title),
                "description": description,
                "duration": duration_seconds,
                "view_count": view_count,
                "like_count": -1,  # Not available in search results
                "comment_count": -1,  # Not available in search results
                "published_time": published_time_text,
                "thumbnail_url": thumbnail_url,
                "video_url": f"https://www.youtube.com/watch?v={video_id}",
                "channel_id": channel_id,
                "channel_name": channel_name,
                "channel_url": f"https://www.youtube.com{channel_url}" if channel_url else "",
            }

        except Exception as e:
            logger.error(f"Failed to extract video info: {e}")
            return None

    async def get_video_details(self, video_id: str) -> Optional[Dict]:
        """
        Get detailed video information

        Args:
            video_id: YouTube video ID

        Returns:
            Detailed video information
        """
        try:
            # Use the player API to get video details
            data = {"videoId": video_id}

            response = await self._make_api_request("player", data)

            video_details = response.get("videoDetails", {})
            if not video_details:
                return None

            # Extract basic video information
            title = video_details.get("title", "")
            description = video_details.get("shortDescription", "")
            duration = int(video_details.get("lengthSeconds", 0))
            view_count = int(video_details.get("viewCount", 0))

            # Extract channel information
            channel_id = video_details.get("channelId", "")
            channel_name = video_details.get("author", "")

            # Extract thumbnail
            thumbnails = video_details.get("thumbnail", {}).get("thumbnails", [])
            thumbnail_url = extract_thumbnail_url(thumbnails)

            return {
                "video_id": video_id,
                "title": process_youtube_text(title),
                "description": process_youtube_text(description),
                "duration": duration,
                "view_count": view_count,
                "like_count": 0,  # Would need additional API call
                "comment_count": 0,  # Would need additional API call
                "published_time": "",  # Not available in player API
                "thumbnail_url": thumbnail_url,
                "video_url": f"https://www.youtube.com/watch?v={video_id}",
                "channel_id": channel_id,
                "channel_name": channel_name,
                "channel_url": f"https://www.youtube.com/channel/{channel_id}" if channel_id else "",
                "keywords": video_details.get("keywords", []),
                "category": video_details.get("category", ""),
                "is_live": video_details.get("isLiveContent", False),
            }

        except Exception as e:
            logger.error(f"Failed to get video details for {video_id}: {e}")
            return None

    async def get_video_comments(
            self,
            video_id: str,
            max_comments: int = 200,
            continuation_token: Optional[str] = None,
            sort_by: int = 0,  # 0 = popular, 1 = recent
            sleep_time: float = 0.1
    ) -> List[Dict]:
        """
        Get comments for a YouTube video with full pagination support

        Args:
            video_id: YouTube video ID
            max_comments: Maximum number of comments to fetch (0 for all)
            continuation_token: Token for pagination
            sort_by: Comment sorting (0=popular, 1=recent)
            sleep_time: Sleep time between requests

        Returns:
            List of simplified comment information
        """
        try:
            comments = []
            continuations = []

            if continuation_token:
                # Use provided continuation token
                continuations.append(continuation_token)
            else:
                # Initial request - need to navigate to video page first to get comments section
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                response = await self._make_request("GET", video_url, headers=self.default_headers, raw_response=True)
                html_content = response.text

                # Extract initial data from the page
                initial_data = self._extract_initial_data_from_html(html_content)
                if not initial_data:
                    logger.error("Failed to extract initial data from video page")
                    return []

                # Find comments section
                continuation_endpoint = self._find_comments_continuation(initial_data, sort_by)
                if not continuation_endpoint:
                    logger.warning(f"No comments found for video {video_id}")
                    return []

                continuations.append(continuation_endpoint)

            # Process all continuation tokens
            while continuations:
                if max_comments > 0 and len(comments) >= max_comments:
                    break

                current_continuation = continuations.pop(0)
                # Make API request for comments
                data = {"continuation": current_continuation}
                response = await self._make_api_request("next", data)

                if not response:
                    break

                # Check for errors
                error_messages = self._search_dict_recursive(response, 'externalErrorMessage')
                if error_messages:
                    logger.error(f"YouTube API error: {error_messages[0]}")
                    break

                # Process response actions to find more comments and continuations
                actions = []
                actions.extend(self._search_dict_recursive(response, 'reloadContinuationItemsCommand'))
                actions.extend(self._search_dict_recursive(response, 'appendContinuationItemsAction'))

                # Process each action to extract comments and find new continuations
                for action in actions:
                    target_id = action.get('targetId', '')
                    continuation_items = action.get('continuationItems', [])

                    # Process continuations for comments and replies
                    if target_id in ['comments-section', 'engagement-panel-comments-section',
                                     'shorts-engagement-panel-comments-section']:
                        for item in continuation_items:
                            # Look for continuation endpoints for more comments
                            continuation_endpoints = self._search_dict_recursive(item, 'continuationEndpoint')
                            for endpoint in continuation_endpoints:
                                if 'continuationCommand' in endpoint:
                                    token = endpoint['continuationCommand']['token']
                                    if token not in continuations:
                                        continuations.insert(0, token)  # Insert at beginning for breadth-first

                    # Process 'Show more replies' buttons
                    elif target_id.startswith('comment-replies-item'):
                        for item in continuation_items:
                            if 'continuationItemRenderer' in item:
                                button_renderers = self._search_dict_recursive(item, 'buttonRenderer')
                                for button in button_renderers:
                                    command = button.get('command', {})
                                    if 'continuationCommand' in command:
                                        token = command['continuationCommand']['token']
                                        if token not in continuations:
                                            continuations.append(token)

                # Extract comment entity payloads for new comment format
                comment_entities = {}
                for payload in self._search_dict_recursive(response, 'commentEntityPayload'):
                    if 'properties' in payload and 'commentId' in payload['properties']:
                        comment_id = payload['properties']['commentId']
                        comment_entities[comment_id] = payload

                # Extract toolbar states
                toolbar_states = {}
                for payload in self._search_dict_recursive(response, 'engagementToolbarStateEntityPayload'):
                    if 'key' in payload:
                        toolbar_states[payload['key']] = payload

                # Process comment entities and extract comment information
                batch_comments = []
                for comment_id in comment_entities:
                    if max_comments > 0 and len(comments) + len(batch_comments) >= max_comments:
                        break

                    entity = comment_entities[comment_id]
                    comment_info = self._extract_comment_from_entity(entity, toolbar_states)
                    if comment_info:
                        batch_comments.append(comment_info)

                # Reverse to maintain chronological order (YouTube returns in reverse)
                batch_comments.reverse()
                comments.extend(batch_comments)

                logger.info(f"Fetched {len(batch_comments)} comments, total: {len(comments)}")

                # Sleep between requests to avoid rate limiting
                if continuations and sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            return comments[:max_comments] if max_comments > 0 else comments

        except Exception as e:
            logger.error(f"Failed to get comments for video {video_id}: {e}")
            return []

    def _extract_initial_data_from_html(self, html_content: str) -> Optional[Dict]:
        """Extract ytInitialData from HTML content"""
        try:
            # Pattern for ytInitialData
            pattern = r'(?:window\s*\[\s*["\']ytInitialData["\']\s*\]|ytInitialData)\s*=\s*({.+?})\s*;\s*(?:var\s+meta|</script|\n)'
            match = re.search(pattern, html_content)
            if match:
                return json.loads(match.group(1))
            return None
        except Exception as e:
            logger.error(f"Failed to extract initial data: {e}")
            return None

    def _find_comments_continuation(self, initial_data: Dict, sort_by: int = 1) -> Optional[str]:
        """Find comments section continuation token"""
        try:
            # Look for itemSectionRenderer in the data
            for item_section in self._search_dict_recursive(initial_data, 'itemSectionRenderer'):
                for continuation_renderer in self._search_dict_recursive(item_section, 'continuationItemRenderer'):
                    continuation_endpoint = continuation_renderer.get('continuationEndpoint', {})
                    if continuation_endpoint:
                        # Check if we need to handle sort menu
                        sort_menu = None
                        for sort_filter in self._search_dict_recursive(initial_data, 'sortFilterSubMenuRenderer'):
                            sort_menu = sort_filter.get('subMenuItems', [])
                            break

                        if sort_menu and sort_by < len(sort_menu):
                            # Use the specified sort option
                            sort_endpoint = sort_menu[sort_by].get('serviceEndpoint', {})
                            if 'continuationCommand' in sort_endpoint:
                                return sort_endpoint['continuationCommand']['token']

                        # Fallback to default continuation
                        if 'continuationCommand' in continuation_endpoint:
                            return continuation_endpoint['continuationCommand']['token']

            return None
        except Exception as e:
            logger.error(f"Failed to find comments continuation: {e}")
            return None

    def _search_dict_recursive(self, data: Any, search_key: str) -> List[Any]:
        """Recursively search for a key in nested dict/list structure"""
        results = []
        stack = [data]

        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                for key, value in current.items():
                    if key == search_key:
                        results.append(value)
                    else:
                        stack.append(value)
            elif isinstance(current, list):
                stack.extend(current)

        return results

    def _extract_comment_from_entity(self, entity: Dict, toolbar_states: Dict) -> Optional[Dict]:
        """Extract comment info from commentEntityPayload format"""
        try:
            properties = entity.get('properties', {})
            author = entity.get('author', {})
            toolbar = entity.get('toolbar', {})

            comment_id = properties.get('commentId', '')
            content = properties.get('content', {}).get('content', '')
            published_time = properties.get('publishedTime', '')

            # Author info
            author_name = author.get('displayName', '')
            author_channel_id = author.get('channelId', '')
            author_avatar = author.get('avatarThumbnailUrl', '')

            # Engagement info
            like_count_text = toolbar.get('likeCountNotliked', '0').strip() or "0"
            like_count = self._parse_count_string(like_count_text)
            reply_count = toolbar.get('replyCount', 0)

            # Check if comment is hearted
            toolbar_state_key = properties.get('toolbarStateKey', '')
            is_hearted = False
            if toolbar_state_key in toolbar_states:
                heart_state = toolbar_states[toolbar_state_key].get('heartState', '')
                is_hearted = heart_state == 'TOOLBAR_HEART_STATE_HEARTED'

            # Check if it's a reply (comment ID contains '.')
            is_reply = '.' in comment_id

            return {
                "comment_id": comment_id,
                "content": process_youtube_text(content),
                "author_name": author_name,
                "author_channel_id": author_channel_id,
                "author_avatar": author_avatar,
                "like_count": like_count,
                "reply_count": reply_count,
                "published_time": published_time,
                "is_hearted": is_hearted,
                "is_reply": is_reply,
                "time_parsed": self._parse_time_string(published_time)
            }

        except Exception as e:
            logger.error(f"Failed to extract comment from entity: {e}")
            return None

    def _parse_count_string(self, count_str: str) -> int:
        """Parse YouTube count strings like '1.2K', '500', etc."""
        try:
            if not count_str or count_str == '0':
                return 0

            count_str = count_str.strip().upper()

            # Handle K, M, B suffixes
            multipliers = {'K': 1000, 'M': 1000000, 'B': 1000000000}

            for suffix, multiplier in multipliers.items():
                if count_str.endswith(suffix):
                    number_part = count_str[:-1]
                    return int(float(number_part) * multiplier)

            # Handle comma-separated numbers
            count_str = count_str.replace(',', '')
            return int(count_str)

        except (ValueError, AttributeError):
            return 0

    def _parse_time_string(self, time_str: str) -> Optional[float]:
        """Parse time string and return timestamp"""
        try:
            if not time_str:
                return None

            # Remove any parenthetical content
            clean_time = time_str.split('(')[0].strip()

            # Try to parse with dateparser if available
            try:
                import dateparser
                parsed = dateparser.parse(clean_time)
                if parsed:
                    return parsed.timestamp()
            except ImportError:
                pass

            return None
        except Exception:
            return None

    async def search_all_videos(
            self,
            query: str,
            sleep_time: float = 0.1
    ) -> List[Dict]:
        """
        Search for all available YouTube videos for a query (no limit)

        Args:
            query: Search query
            sleep_time: Sleep time between requests

        Returns:
            List of all available video information
        """
        return await self.search_videos(
            query=query,
            max_results=0,  # 0 means no limit
            sleep_time=sleep_time
        )

    async def get_all_video_comments(
            self,
            video_id: str,
            sort_by: int = 1,  # 0 = popular, 1 = recent
            sleep_time: float = 0.1
    ) -> List[Dict]:
        """
        Get all comments for a YouTube video (no limit)

        Args:
            video_id: YouTube video ID
            sort_by: Comment sorting (0=popular, 1=recent)
            sleep_time: Sleep time between requests

        Returns:
            List of all comments for the video
        """
        return await self.get_video_comments(
            video_id=video_id,
            max_comments=0,  # 0 means no limit
            sort_by=sort_by,
            sleep_time=sleep_time
        )

    def _extract_continuation_tokens(self, data: Any) -> List[str]:
        """
        Extract all continuation tokens from YouTube API response

        Args:
            data: YouTube API response data

        Returns:
            List of continuation tokens
        """
        tokens = []

        # Search for continuation endpoints
        continuation_endpoints = self._search_dict_recursive(data, 'continuationEndpoint')
        for endpoint in continuation_endpoints:
            if 'continuationCommand' in endpoint:
                token = endpoint['continuationCommand']['token']
                if token and token not in tokens:
                    tokens.append(token)

        # Search for continuation commands
        continuation_commands = self._search_dict_recursive(data, 'continuationCommand')
        for command in continuation_commands:
            token = command.get('token')
            if token and token not in tokens:
                tokens.append(token)

        return tokens

    def _extract_comment_info(self, comment_data: Dict) -> Optional[Dict]:
        """Extract simplified comment information from traditional YouTube comment data"""
        try:
            # Extract comment ID
            comment_id = comment_data.get("commentId", "")

            # Extract comment text
            content_text = comment_data.get("contentText", {})
            text = ""
            if "runs" in content_text:
                text = "".join([run.get("text", "") for run in content_text["runs"]])
            elif "simpleText" in content_text:
                text = content_text["simpleText"]

            # Extract author information
            author_text = comment_data.get("authorText", {}).get("simpleText", "")
            author_thumbnail = comment_data.get("authorThumbnail", {}).get("thumbnails", [])
            author_avatar = extract_thumbnail_url(author_thumbnail)

            # Extract author channel ID if available
            author_endpoint = comment_data.get("authorEndpoint", {}).get("commandMetadata", {}).get(
                "webCommandMetadata", {})
            author_url = author_endpoint.get("url", "")
            author_channel_id = extract_channel_id_from_url(author_url) if author_url else ""

            # Extract like count
            like_count_text = comment_data.get("voteCount", {}).get("simpleText", "0")
            like_count = self._parse_count_string(like_count_text)

            # Extract published time
            published_time_data = comment_data.get("publishedTimeText", {})
            published_time = ""
            if "runs" in published_time_data:
                published_time = published_time_data["runs"][0].get("text", "")
            elif "simpleText" in published_time_data:
                published_time = published_time_data["simpleText"]

            # Extract reply count
            reply_count = 0
            reply_text = comment_data.get("replyCount", 0)
            if isinstance(reply_text, dict):
                reply_text = reply_text.get("simpleText", "0")
            if isinstance(reply_text, str):
                reply_count = self._parse_count_string(reply_text)
            elif isinstance(reply_text, int):
                reply_count = reply_text

            # Check if comment is hearted by creator
            is_hearted = False
            if "actionButtons" in comment_data:
                buttons = comment_data["actionButtons"].get("commentActionButtonsRenderer", {})
                heart_button = buttons.get("creatorHeart", {})
                is_hearted = bool(heart_button.get("creatorHeartRenderer", {}))

            # Check if it's a reply (comment ID contains '.')
            is_reply = '.' in comment_id

            return {
                "comment_id": comment_id,
                "content": process_youtube_text(text),
                "author_name": author_text,
                "author_channel_id": author_channel_id,
                "author_avatar": author_avatar,
                "like_count": like_count,
                "reply_count": reply_count,
                "published_time": published_time,
                "is_hearted": is_hearted,
                "is_reply": is_reply,
                "time_parsed": self._parse_time_string(published_time)
            }

        except Exception as e:
            logger.error(f"Failed to extract comment info: {e}")
            return None

    def _build_channel_url(self, channel_id: str) -> str:
        clean_id = channel_id.strip()

        if clean_id.startswith('@'):
            return f"https://www.youtube.com/{clean_id}"

        if re.match(r'^UC[a-zA-Z0-9_-]{22}$', clean_id):
            return f"https://www.youtube.com/channel/{clean_id}"

        if re.match(r'^[a-zA-Z0-9_-]{24}$', clean_id):
            return f"https://www.youtube.com/channel/{clean_id}"

        if re.match(r'^[a-zA-Z0-9_-]+$', clean_id):
            return f"https://www.youtube.com/@{clean_id}"

        if '/' in clean_id:
            return f"https://www.youtube.com/{clean_id}"

        return f"https://www.youtube.com/@{clean_id}"

    async def get_channel_info(self, channel_id: str) -> Optional[Dict]:
        """
        Get YouTube channel information
        
        Args:
            channel_id: YouTube channel ID
            
        Returns:
            Simplified channel information
        """
        try:
            # Navigate to channel page to get information
            channel_url = self._build_channel_url(channel_id)

            response = await self._make_request(
                "GET", channel_url, headers=self.default_headers, raw_response=True
            )
            html_content = response.text
            initial_data = extract_initial_data(html_content)

            if not initial_data:
                return None

            # Extract channel information from initial data
            metadata = initial_data.get("metadata", {}).get("channelMetadataRenderer", {})
            header = initial_data.get("header", {})
            # Try different header types
            channel_header = (header.get("c4TabbedHeaderRenderer") or
                              header.get("pageHeaderRenderer") or
                              header.get("interactiveTabbedHeaderRenderer") or {})

            title = metadata.get("title", "") or channel_header.get("title", "")
            description = metadata.get("description", "")

            # Extract subscriber count and video count from pageHeaderRenderer if available
            subscriber_count = 0
            video_count = 0

            if "pageHeaderRenderer" in header:
                page_header = header["pageHeaderRenderer"]
                metadata_rows = page_header.get("content", {}).get("pageHeaderViewModel", {}).get("metadata", {}).get(
                    "contentMetadataViewModel", {}).get("metadataRows", [])

                if len(metadata_rows) > 1:
                    # Second row contains subscriber and video counts
                    metadata_parts = metadata_rows[1].get("metadataParts", [])
                    if len(metadata_parts) > 0:
                        # Subscriber count (e.g., "21.2万位订阅者")
                        subscriber_text = metadata_parts[0].get("text", {}).get("content", "")
                        subscriber_count = subscriber_text.replace("位订阅者", "").replace("订阅者", "").replace(
                            "subscribers", "").strip()

                    if len(metadata_parts) > 1:
                        # Video count (e.g., "67 个视频")
                        video_text = metadata_parts[1].get("text", {}).get("content", "")
                        video_count = video_text.replace("个视频", "").replace("视频", "").replace("videos", "").strip()

            # Extract avatar
            avatar_thumbnails = channel_header.get("avatar", {}).get("thumbnails", [])
            avatar_url = extract_thumbnail_url(avatar_thumbnails)

            # Extract banner
            banner_thumbnails = channel_header.get("banner", {}).get("thumbnails", [])
            banner_url = extract_thumbnail_url(banner_thumbnails)

            return {
                "channel_id": channel_id,
                "title": process_youtube_text(title),
                "description": process_youtube_text(description),
                "subscriber_count": subscriber_count,
                "video_count": video_count,
                "avatar_url": avatar_url,
                "banner_url": banner_url,
                "channel_url": channel_url,
                "verified": False,  # Would need additional processing
            }

        except Exception as e:
            logger.error(f"Failed to get channel info for {channel_id}: {e}")
            return None

    async def get_channel_videos(
            self,
            channel_id: str,
            max_videos: int = 20,
            continuation_token: Optional[str] = None,
            sleep_time: float = 0.1
    ) -> List[Dict]:
        """
        Get videos from a YouTube channel with pagination support
        
        Args:
            channel_id: YouTube channel ID (can be UC... format, @username, or custom name)
            max_videos: Maximum number of videos to fetch (0 for all available)
            continuation_token: Token for pagination
            sleep_time: Sleep time between requests
            
        Returns:
            List of simplified video information
        """
        try:
            videos = []
            continuations = []

            if continuation_token:
                # Use provided continuation token
                continuations.append(continuation_token)
            else:
                # Initial request to get videos page and extract initial data
                videos_url = f"https://www.youtube.com/@{channel_id}/videos"
                response = await self._make_request(
                    "GET", videos_url, headers=self.default_headers, raw_response=True
                )

                html_content = response.text
                initial_data = extract_initial_data(html_content)
                if not initial_data:
                    logger.error("Failed to extract initial data from videos page")
                    return []

                # Find video renderers in the initial page data
                video_renderers = self._find_video_renderers(initial_data)

                for video_data in video_renderers:
                    if max_videos > 0 and len(videos) >= max_videos:
                        break
                    video_info = self._extract_video_info(video_data)
                    if video_info:
                        video_info['channel_id'] = channel_id
                        videos.append(video_info)

                # Extract continuation tokens for more results
                continuation_tokens = self._extract_continuation_tokens(initial_data)
                continuations.extend(continuation_tokens)

                logger.info(
                    f"Initial page: extracted {len(videos)} videos, found {len(continuations)} continuation tokens")

            # Process continuation tokens for more videos
            while continuations and (max_videos == 0 or len(videos) < max_videos):
                current_continuation = continuations.pop(0)

                # Make API request with continuation token
                data = {"continuation": current_continuation}
                response = await self._make_api_request("browse", data)

                if not response:
                    break

                # Extract videos from continuation response
                video_renderers = self._find_video_renderers(response)
                batch_videos = []

                for video_data in video_renderers:
                    if max_videos > 0 and len(videos) + len(batch_videos) >= max_videos:
                        break
                    video_info = self._extract_video_info(video_data)
                    if video_info:
                        video_info['channel_id'] = channel_id
                        batch_videos.append(video_info)

                videos.extend(batch_videos)

                # Look for more continuation tokens
                continuation_tokens = self._extract_continuation_tokens(response)
                for token in continuation_tokens:
                    if token not in continuations:
                        continuations.append(token)

                logger.info(f"Continuation batch: fetched {len(batch_videos)} videos, total: {len(videos)}")

                # Sleep between requests to avoid rate limiting
                if continuations and sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            return videos[:max_videos] if max_videos > 0 else videos

        except Exception as e:
            logger.error(f"Failed to get channel videos for {channel_id}: {e}")
            return []

    async def get_trending_videos(self) -> List[Dict]:
        """
        Get trending YouTube videos
        
        Args:
            max_videos: Maximum number of videos to fetch
            
        Returns:
            List of simplified trending video information
        """
        try:
            data = {"browseId": "FEtrending"}

            response = await self._make_api_request("browse", data)

            videos = []

            # Navigate to trending video list
            contents = response.get("contents", {}).get("twoColumnBrowseResultsRenderer", {}).get("tabs", [])
            for tab in contents:
                tab_content = tab.get("tabRenderer", {}).get("content", {})
                sections = tab_content.get("sectionListRenderer", {}).get("contents", [])

                for section in sections:
                    items_up = section.get("itemSectionRenderer", {}).get("contents", [])
                    for item_up in items_up:
                        items = item_up.get('shelfRenderer', {}).get(
                            'content').get('expandedShelfContentsRenderer').get('items', [])
                        for item in items:
                            # Check for different video renderer types
                            video_data = (item.get("videoRenderer") or
                                          item.get("compactVideoRenderer") or
                                          item.get("gridVideoRenderer"))
                            if video_data:
                                video_info = self._extract_video_info(video_data)
                                if video_info:
                                    videos.append(video_info)

            return videos

        except Exception as e:
            logger.error(f"Failed to get trending videos: {e}")
            return []

    async def get_video_transcript(self, video_id: str, languages: Optional[List[str]] = None) -> Optional[
        Dict[str, List[Dict]]]:
        """
        Get transcript for a YouTube video
        
        Args:
            video_id: YouTube video ID (not the full URL)
            languages: List of language codes to try (default: ['en'])
            
        Returns:
            Dictionary with language codes as keys and transcript raw data as values
            Returns None if no transcripts are available
        """
        try:
            if languages is None:
                languages = ['en']

            # Create YouTubeTranscriptApi instance
            ytt_api = YouTubeTranscriptApi()

            # List available transcripts to check what's available
            transcript_list = ytt_api.list(video_id)
            available_languages = [transcript.language_code for transcript in transcript_list]

            logger.info(f"Available transcript languages for video {video_id}: {available_languages}")

            # Filter requested languages to only include available ones
            valid_languages = [lang for lang in languages if lang in available_languages]

            if not valid_languages:
                logger.warning(f"None of the requested languages {languages} are available for video {video_id}")
                return None

            # Fetch transcripts for each valid language
            result = {}
            for language in valid_languages:
                try:
                    # Find transcript for this specific language
                    transcript = transcript_list.find_transcript([language])
                    fetched_transcript = transcript.fetch()

                    # Convert to raw data format
                    raw_data = fetched_transcript.to_raw_data()
                    result[language] = raw_data

                    logger.info(f"Successfully fetched transcript for video {video_id} in language {language}")

                except Exception as lang_error:
                    logger.warning(f"Failed to fetch transcript for language {language}: {lang_error}")
                    continue

            return result if result else None

        except Exception as e:
            logger.error(f"Failed to get transcript for video {video_id}: {e}")
            return None

    async def close(self):
        if self.browser_session and self.target_id and self.new_tab:
            try:
                logger.info(f"Close target id: {self.target_id}")
                await self.browser_session.cdp_client.send.Target.closeTarget(params={'targetId': self.target_id})
            except Exception as e:
                logger.warning(f"Error closing target {self.target_id}: {e}")
