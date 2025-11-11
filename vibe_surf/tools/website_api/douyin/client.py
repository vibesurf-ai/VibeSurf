import asyncio
import json
import copy
import pdb
import time
import urllib.parse
import os
from typing import Dict, List, Optional, Callable, Union, Any
import httpx
import random
from tenacity import retry, stop_after_attempt, wait_fixed

try:
    import execjs

    HAS_EXECJS = True
except ImportError:
    HAS_EXECJS = False

from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.logger import get_logger

from .helpers import (
    SearchChannelType, SearchSortType, PublishTimeType,
    generate_web_id, generate_trace_id, create_common_params,
    extract_cookies_from_browser, create_referer_url,
    extract_aweme_media_urls, DouyinError, NetworkError,
    DataExtractionError, AuthenticationError, RateLimitError,
    VerificationError
)

logger = get_logger(__name__)


class DouyinApiClient:
    """
    Douyin API client with integrated browser session management.
    This client handles API communication through browser session for authentication.
    """

    def __init__(self, browser_session: AgentBrowserSession, timeout: int = 60, proxy: Optional[str] = None):
        """
        Initialize the Douyin API client
        
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
        self._host = "https://www.douyin.com"

        # Default headers
        self.default_headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            "Host": "www.douyin.com",
            "Origin": "https://www.douyin.com/",
            "Referer": "https://www.douyin.com/",
            "Content-Type": "application/json;charset=UTF-8",
        }
        self.cookies = {}

    async def check_login(self) -> bool:
        """Check if login state is valid using multiple methods"""
        try:
            ret = await self.search_content_by_keyword("IT trends")
            return ret and len(ret) > 0
        except Exception as e:
            logger.error(f"Failed to check Weibo login status: {e}")
            return False

    async def setup(self, target_id: Optional[str] = None):
        """
        Setup Douyin client by navigating to the site and extracting cookies
        
        Args:
            target_id: Specific target ID to use, or None to create new
            
        Raises:
            AuthenticationError: If unable to access Douyin properly
        """
        try:
            if self.target_id and self.cookies:
                logger.info("Douyin client already setup. Returning!")
                return

            if target_id:
                self.target_id = target_id
            else:
                self.target_id = await self.browser_session.navigate_to_url(
                    "https://www.douyin.com/", new_tab=True
                )
                await asyncio.sleep(2)  # Wait for page to load
                self.new_tab = True

            cdp_session = await self.browser_session.get_or_create_cdp_session(target_id=self.target_id)
            result = await asyncio.wait_for(
                cdp_session.cdp_client.send.Storage.getCookies(session_id=cdp_session.session_id),
                timeout=8.0
            )
            web_cookies = result.get('cookies', [])
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
            cookie_str, cookie_dict = extract_cookies_from_browser(web_cookies)
            if cookie_str:
                self.default_headers["Cookie"] = cookie_str
            self.cookies = cookie_dict
            is_logged_in = await self.check_login_status()
            if not is_logged_in:
                self.cookies = {}
                del self.default_headers["Cookie"]
                raise AuthenticationError(f"Please login in [抖音]({self._host}) first!")

            logger.info(f"Douyin client setup completed with {len(cookie_dict)} cookies")

        except Exception as e:
            logger.error(f"Failed to setup Douyin client: {e}")
            raise AuthenticationError(f"Douyin client setup failed: {e}")

    async def _get_local_storage_token(self) -> Optional[str]:
        """Get msToken from browser local storage"""
        try:
            cdp_session = await self.browser_session.get_or_create_cdp_session(target_id=self.target_id)
            result = await cdp_session.cdp_client.send.Runtime.evaluate(
                params={
                    'expression': "window.localStorage.getItem('xmst')",
                    'returnByValue': True,
                    'awaitPromise': True
                },
                session_id=cdp_session.session_id,
            )
            return result.get('result', {}).get('value')
        except Exception as e:
            logger.warning(f"Failed to get local storage token: {e}")
            return None

    def _init_js_context(self):
        """Initialize JavaScript context for signature generation"""
        if not HAS_EXECJS:
            logger.warning("execjs not available, signature generation disabled")
            return None

        try:
            js_file_path = os.path.join(os.path.dirname(__file__), 'douyin.js')
            if not os.path.exists(js_file_path):
                logger.warning(f"douyin.js file not found at {js_file_path}")
                return None

            with open(js_file_path, 'r', encoding='utf-8-sig') as f:
                js_content = f.read()

            return execjs.compile(js_content)
        except Exception as e:
            logger.error(f"Failed to initialize JS context: {e}")
            return None

    async def _get_a_bogus_signature(self, uri: str, params: str, post_data: Dict = None) -> str:
        """
        Get a-bogus signature using JavaScript execution
        
        Args:
            uri: Request URI
            params: URL parameters string
            post_data: POST data if applicable
            
        Returns:
            a-bogus signature string
        """
        try:
            if not hasattr(self, '_js_context'):
                self._js_context = self._init_js_context()

            if not self._js_context:
                return ""

            user_agent = self.default_headers.get('User-Agent', '')

            # Determine the signature function name based on URI
            sign_function_name = "sign_datail"
            if "/reply" in uri:
                sign_function_name = "sign_reply"

            # Call the JavaScript function
            a_bogus = self._js_context.call(sign_function_name, params, user_agent)
            return a_bogus or ""

        except Exception as e:
            logger.warning(f"Failed to generate a-bogus signature: {e}")
            return ""

    async def _prepare_request_params(self, uri: str, params: Optional[Dict] = None,
                                      headers: Optional[Dict] = None, request_method: str = "GET",
                                      post_data: Optional[Dict] = None):
        """
        Prepare request parameters with common Douyin parameters and signatures
        
        Args:
            uri: Request URI
            params: Request parameters
            headers: Request headers
            request_method: HTTP method
            post_data: POST data if applicable
        """
        if not params:
            params = {}

        headers = headers or copy.deepcopy(self.default_headers)

        # Add common parameters
        common_params = create_common_params()

        # Add msToken from local storage
        ms_token = await self._get_local_storage_token()
        if ms_token:
            common_params["msToken"] = ms_token

        params.update(common_params)

        # Generate query string
        query_string = urllib.parse.urlencode(params)

        # Get a-bogus signature
        post_data = post_data or {}
        if "/v1/web/general/search" not in uri:
            a_bogus = await self._get_a_bogus_signature(uri, query_string, post_data)
            params["a_bogus"] = a_bogus

        return params, headers

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def _make_request(self, method: str, url: str, **kwargs) -> Union[str, Dict]:
        """
        Make HTTP request with error handling and retries
        
        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional request parameters
            
        Returns:
            Response data
        """
        async with httpx.AsyncClient(proxy=self.proxy) as client:
            response = await client.request(method, url, timeout=self.timeout, **kwargs)

        # Handle common error responses
        if response.text == "" or response.text == "blocked":
            logger.error(f"Request blocked, response.text: {response.text}")
            raise VerificationError("Account may be blocked or requires verification")

        try:
            data = response.json()

            # Check for successful response
            if response.status_code == 200:
                return data
            else:
                error_msg = data.get("message", "Request failed")
                raise DataExtractionError(f"API error: {error_msg}")

        except json.JSONDecodeError:
            if response.status_code == 200:
                return response.text
            else:
                raise DataExtractionError(f"Invalid response: {response.text[:200]}")

    async def get_request(self, uri: str, params: Optional[Dict] = None, headers: Optional[Dict] = None):
        """Make GET request with Douyin-specific parameter preparation"""
        params, headers = await self._prepare_request_params(uri, params, headers, "GET")
        return await self._make_request("GET", f"{self._host}{uri}", params=params, headers=headers)

    async def post_request(self, uri: str, data: Dict, headers: Optional[Dict] = None):
        """Make POST request with Douyin-specific parameter preparation"""
        data, headers = await self._prepare_request_params(uri, data, headers, "POST", post_data=data)
        return await self._make_request("POST", f"{self._host}{uri}", data=data, headers=headers)

    async def search_content_by_keyword(
            self,
            keyword: str,
            offset: int = 0,
            search_channel: SearchChannelType = SearchChannelType.GENERAL,
            sort_type: SearchSortType = SearchSortType.GENERAL,
            publish_time: PublishTimeType = PublishTimeType.UNLIMITED,
            search_id: str = "",
    ) -> List[Dict]:
        """
        Search content by keyword using Douyin Web Search API
        
        Args:
            keyword: Search keyword
            offset: Pagination offset
            search_channel: Search channel type
            sort_type: Sort method
            publish_time: Time filter
            search_id: Search session ID
            
        Returns:
            List of simplified aweme data
        """
        query_params = {
            'search_channel': search_channel.value,
            'enable_history': '1',
            'keyword': keyword,
            'search_source': 'tab_search',
            'query_correct_type': '1',
            'is_filter_search': '0',
            'offset': offset,
            'count': '15',
            'need_filter_settings': '1',
            'list_type': 'multi',
            'search_id': search_id,
        }

        # Add filters if not default
        if sort_type.value != SearchSortType.GENERAL.value or publish_time.value != PublishTimeType.UNLIMITED.value:
            query_params["filter_selected"] = json.dumps({
                "sort_type": str(sort_type.value),
                "publish_time": str(publish_time.value)
            })
            query_params["is_filter_search"] = 1
            query_params["search_source"] = "tab_search"

        referer_url = create_referer_url(keyword=keyword)
        headers = copy.copy(self.default_headers)
        headers["Referer"] = referer_url

        search_result = await self.get_request("/aweme/v1/web/general/search/single/", query_params, headers)

        # Return simplified aweme list
        aweme_list = []
        for post_item in search_result.get("data", []):
            try:
                aweme_info: Dict = (
                            post_item.get("aweme_info") or post_item.get("aweme_mix_info", {}).get("mix_items")[0])
            except (TypeError, IndexError):
                continue

            if not aweme_info or not aweme_info.get("aweme_id"):
                continue

            user_info = aweme_info.get("author", {})
            interact_info = aweme_info.get("statistics", {})

            # Simplified aweme data
            aweme_data = {
                "aweme_id": aweme_info.get("aweme_id"),
                "aweme_type": str(aweme_info.get("aweme_type", "")),
                "title": aweme_info.get("desc", ""),
                "desc": aweme_info.get("desc", ""),
                "create_time": aweme_info.get("create_time"),
                "user_id": user_info.get("uid"),
                "sec_uid": user_info.get("sec_uid"),
                "short_user_id": user_info.get("short_id"),
                "user_unique_id": user_info.get("unique_id"),
                "nickname": user_info.get("nickname"),
                "avatar": user_info.get("avatar_thumb", {}).get("url_list", [""])[0],
                "liked_count": str(interact_info.get("digg_count", 0)),
                "collected_count": str(interact_info.get("collect_count", 0)),
                "comment_count": str(interact_info.get("comment_count", 0)),
                "share_count": str(interact_info.get("share_count", 0)),
                "ip_location": aweme_info.get("ip_label", ""),
                "aweme_url": f"https://www.douyin.com/video/{aweme_info.get('aweme_id')}",
            }
            aweme_list.append(aweme_data)

        return aweme_list

    async def fetch_video_details(self, aweme_id: str) -> Dict:
        """
        Fetch detailed video information by aweme ID
        
        Args:
            aweme_id: Video ID
            
        Returns:
            Simplified video details data
        """
        params = {"aweme_id": aweme_id}
        headers = copy.copy(self.default_headers)
        if "Origin" in headers:
            del headers["Origin"]

        response = await self.get_request("/aweme/v1/web/aweme/detail/", params, headers)
        aweme_detail = response.get("aweme_detail", {})

        if not aweme_detail:
            return {}

        user_info = aweme_detail.get("author", {})
        interact_info = aweme_detail.get("statistics", {})

        return {
            "aweme_id": aweme_detail.get("aweme_id"),
            "aweme_type": str(aweme_detail.get("aweme_type", "")),
            "title": aweme_detail.get("desc", ""),
            "desc": aweme_detail.get("desc", ""),
            "create_time": aweme_detail.get("create_time"),
            "user_id": user_info.get("uid"),
            "sec_uid": user_info.get("sec_uid"),
            "short_user_id": user_info.get("short_id"),
            "user_unique_id": user_info.get("unique_id"),
            "nickname": user_info.get("nickname"),
            "avatar": user_info.get("avatar_thumb", {}).get("url_list", [""])[0],
            "liked_count": str(interact_info.get("digg_count", 0)),
            "collected_count": str(interact_info.get("collect_count", 0)),
            "comment_count": str(interact_info.get("comment_count", 0)),
            "share_count": str(interact_info.get("share_count", 0)),
            "ip_location": aweme_detail.get("ip_label", ""),
            "aweme_url": f"https://www.douyin.com/video/{aweme_detail.get('aweme_id')}",
        }

    async def fetch_video_comments(self, aweme_id: str, cursor: int = 0) -> List[Dict]:
        """
        Fetch video comments with pagination
        
        Args:
            aweme_id: Video ID
            cursor: Pagination cursor
            
        Returns:
            List of simplified comments data
        """
        uri = "/aweme/v1/web/comment/list/"
        params = {
            "aweme_id": aweme_id,
            "cursor": cursor,
            "count": 20,
            "item_type": 0
        }

        headers = copy.copy(self.default_headers)
        headers["Referer"] = create_referer_url(aweme_id=aweme_id)

        response = await self.get_request(uri, params, headers)

        # Return simplified comments
        comments = []
        for comment_item in response.get("comments", []):
            if not comment_item.get("cid"):
                continue

            user_info = comment_item.get("user", {})
            avatar_info = (user_info.get("avatar_medium", {}) or
                           user_info.get("avatar_300x300", {}) or
                           user_info.get("avatar_168x168", {}) or
                           user_info.get("avatar_thumb", {}) or {})

            comment_data = {
                "comment_id": comment_item.get("cid"),
                "create_time": comment_item.get("create_time"),
                "ip_location": comment_item.get("ip_label", ""),
                "aweme_id": aweme_id,
                "content": comment_item.get("text"),
                "user_id": user_info.get("uid"),
                "sec_uid": user_info.get("sec_uid"),
                "short_user_id": user_info.get("short_id"),
                "user_unique_id": user_info.get("unique_id"),
                "nickname": user_info.get("nickname"),
                "avatar": avatar_info.get("url_list", [""])[0],
                "sub_comment_count": str(comment_item.get("reply_comment_total", 0)),
                "like_count": comment_item.get("digg_count", 0),
                "parent_comment_id": comment_item.get("reply_id", "0"),
            }
            comments.append(comment_data)

        return comments

    async def fetch_comment_replies(self, aweme_id: str, comment_id: str, cursor: int = 0) -> List[Dict]:
        """
        Fetch replies to a specific comment
        
        Args:
            aweme_id: Video ID
            comment_id: Parent comment ID
            cursor: Pagination cursor
            
        Returns:
            List of simplified reply comments data
        """
        uri = "/aweme/v1/web/comment/list/reply/"
        params = {
            'comment_id': comment_id,
            "cursor": cursor,
            "count": 20,
            "item_type": 0,
            "item_id": aweme_id,
        }

        headers = copy.copy(self.default_headers)
        headers["Referer"] = create_referer_url(aweme_id=aweme_id)

        response = await self.get_request(uri, params, headers)

        # Return simplified reply comments
        replies = []
        for comment_item in response.get("comments", []):
            if not comment_item.get("cid"):
                continue

            user_info = comment_item.get("user", {})
            avatar_info = (user_info.get("avatar_medium", {}) or
                           user_info.get("avatar_300x300", {}) or
                           user_info.get("avatar_168x168", {}) or
                           user_info.get("avatar_thumb", {}) or {})

            reply_data = {
                "comment_id": comment_item.get("cid"),
                "create_time": comment_item.get("create_time"),
                "ip_location": comment_item.get("ip_label", ""),
                "aweme_id": aweme_id,
                "content": comment_item.get("text"),
                "user_id": user_info.get("uid"),
                "sec_uid": user_info.get("sec_uid"),
                "short_user_id": user_info.get("short_id"),
                "user_unique_id": user_info.get("unique_id"),
                "nickname": user_info.get("nickname"),
                "avatar": avatar_info.get("url_list", [""])[0],
                "sub_comment_count": str(comment_item.get("reply_comment_total", 0)),
                "like_count": comment_item.get("digg_count", 0),
                "parent_comment_id": comment_id,
            }
            replies.append(reply_data)

        return replies

    async def fetch_all_video_comments(
            self,
            aweme_id: str,
            fetch_interval: float = 1.0,
            include_replies: bool = False,
            max_comments: int = 1000,
    ) -> List[Dict]:
        """
        Fetch all comments for a video, including replies if requested
        
        Args:
            aweme_id: Video ID
            fetch_interval: Delay between requests
            include_replies: Whether to fetch comment replies
            max_comments: Maximum comments to fetch
            
        Returns:
            List of all simplified comments
        """
        all_comments = []
        has_more = True
        cursor = 0

        while has_more and len(all_comments) < max_comments:
            uri = "/aweme/v1/web/comment/list/"
            params = {
                "aweme_id": aweme_id,
                "cursor": cursor,
                "count": 20,
                "item_type": 0
            }

            headers = copy.copy(self.default_headers)
            headers["Referer"] = create_referer_url(aweme_id=aweme_id)

            comments_data = await self.get_request(uri, params, headers)
            has_more = comments_data.get("has_more", False)
            cursor = comments_data.get("cursor", 0)

            # Get simplified comments from this batch
            batch_comments = []
            for comment_item in comments_data.get("comments", []):
                if not comment_item.get("cid"):
                    continue

                user_info = comment_item.get("user", {})
                avatar_info = (user_info.get("avatar_medium", {}) or
                               user_info.get("avatar_300x300", {}) or
                               user_info.get("avatar_168x168", {}) or
                               user_info.get("avatar_thumb", {}) or {})

                comment_data = {
                    "comment_id": comment_item.get("cid"),
                    "create_time": comment_item.get("create_time"),
                    "ip_location": comment_item.get("ip_label", ""),
                    "aweme_id": aweme_id,
                    "content": comment_item.get("text"),
                    "user_id": user_info.get("uid"),
                    "sec_uid": user_info.get("sec_uid"),
                    "short_user_id": user_info.get("short_id"),
                    "user_unique_id": user_info.get("unique_id"),
                    "nickname": user_info.get("nickname"),
                    "avatar": avatar_info.get("url_list", [""])[0],
                    "sub_comment_count": str(comment_item.get("reply_comment_total", 0)),
                    "like_count": comment_item.get("digg_count", 0),
                    "parent_comment_id": comment_item.get("reply_id", "0"),
                }
                batch_comments.append(comment_data)

            if not batch_comments:
                break

            # Limit comments to max_comments
            remaining_slots = max_comments - len(all_comments)
            if remaining_slots <= 0:
                break

            if len(batch_comments) > remaining_slots:
                batch_comments = batch_comments[:remaining_slots]

            all_comments.extend(batch_comments)

            await asyncio.sleep(fetch_interval)

            # Fetch replies if requested
            if include_replies:
                for comment in batch_comments:
                    reply_count = int(comment.get("sub_comment_count", 0))

                    if reply_count > 0:
                        comment_id = comment.get("comment_id")
                        replies = await self.fetch_comment_replies(aweme_id, comment_id, 0)
                        all_comments.extend(replies)

                        await asyncio.sleep(fetch_interval)

        logger.info(f"Fetched {len(all_comments)} comments for video {aweme_id}")
        return all_comments

    async def fetch_user_info(self, sec_user_id: str) -> Dict:
        """
        Fetch user profile information
        
        Args:
            sec_user_id: User's security ID
            
        Returns:
            Simplified user information data
        """
        uri = "/aweme/v1/web/user/profile/other/"
        params = {
            "sec_user_id": sec_user_id,
            "publish_video_strategy_type": 2,
            "personal_center_strategy": 1,
        }
        response = await self.get_request(uri, params)

        user_data = response.get("user", {})
        if not user_data:
            return {}

        gender_map = {0: "未知", 1: "男", 2: "女"}
        avatar_uri = user_data.get("avatar_300x300", {}).get("uri", "")

        return {
            "user_id": user_data.get("uid"),
            "nickname": user_data.get("nickname"),
            "gender": gender_map.get(user_data.get("gender"), "未知"),
            "avatar": f"https://p3-pc.douyinpic.com/img/{avatar_uri}~c5_300x300.jpeg?from=2956013662" if avatar_uri else "",
            "desc": user_data.get("signature"),
            "ip_location": user_data.get("ip_location"),
            "follows": user_data.get("following_count", 0),
            "fans": user_data.get("max_follower_count", 0),
            "interaction": user_data.get("total_favorited", 0),
            "videos_count": user_data.get("aweme_count", 0),
        }

    async def fetch_user_videos(self, sec_user_id: str, max_cursor: str = "") -> List[Dict]:
        """
        Fetch user's videos with pagination
        
        Args:
            sec_user_id: User's security ID
            max_cursor: Pagination cursor
            
        Returns:
            List of simplified user videos data
        """
        uri = "/aweme/v1/web/aweme/post/"
        params = {
            "sec_user_id": sec_user_id,
            "count": 18,
            "max_cursor": max_cursor,
            "locate_query": "false",
            "publish_video_strategy_type": 2,
        }
        response = await self.get_request(uri, params)

        # Return simplified aweme list
        aweme_list = []
        for aweme_info in response.get("aweme_list", []):
            if not aweme_info.get("aweme_id"):
                continue

            user_info = aweme_info.get("author", {})
            interact_info = aweme_info.get("statistics", {})

            aweme_data = {
                "aweme_id": aweme_info.get("aweme_id"),
                "aweme_type": str(aweme_info.get("aweme_type", "")),
                "title": aweme_info.get("desc", ""),
                "desc": aweme_info.get("desc", ""),
                "create_time": aweme_info.get("create_time"),
                "user_id": user_info.get("uid"),
                "sec_uid": user_info.get("sec_uid"),
                "short_user_id": user_info.get("short_id"),
                "user_unique_id": user_info.get("unique_id"),
                "nickname": user_info.get("nickname"),
                "avatar": user_info.get("avatar_thumb", {}).get("url_list", [""])[0],
                "liked_count": str(interact_info.get("digg_count", 0)),
                "collected_count": str(interact_info.get("collect_count", 0)),
                "comment_count": str(interact_info.get("comment_count", 0)),
                "share_count": str(interact_info.get("share_count", 0)),
                "ip_location": aweme_info.get("ip_label", ""),
                "aweme_url": f"https://www.douyin.com/video/{aweme_info.get('aweme_id')}",
            }
            aweme_list.append(aweme_data)

        return aweme_list

    async def fetch_all_user_videos(
            self,
            sec_user_id: str,
            max_videos: int = 1000
    ) -> List[Dict]:
        """
        Fetch all videos from a user
        
        Args:
            sec_user_id: User's security ID
            max_videos: Maximum videos to fetch
            
        Returns:
            List of all simplified user videos
        """
        all_videos = []
        has_more = True
        max_cursor = ""

        while has_more and len(all_videos) < max_videos:
            uri = "/aweme/v1/web/aweme/post/"
            params = {
                "sec_user_id": sec_user_id,
                "count": 18,
                "max_cursor": max_cursor,
                "locate_query": "false",
                "publish_video_strategy_type": 2,
            }
            videos_data = await self.get_request(uri, params)
            has_more = videos_data.get("has_more", False)
            max_cursor = videos_data.get("max_cursor", "")

            # Get simplified videos from this batch
            batch_videos = []
            for aweme_info in videos_data.get("aweme_list", []):
                if not aweme_info.get("aweme_id"):
                    continue

                user_info = aweme_info.get("author", {})
                interact_info = aweme_info.get("statistics", {})

                aweme_data = {
                    "aweme_id": aweme_info.get("aweme_id"),
                    "aweme_type": str(aweme_info.get("aweme_type", "")),
                    "title": aweme_info.get("desc", ""),
                    "desc": aweme_info.get("desc", ""),
                    "create_time": aweme_info.get("create_time"),
                    "user_id": user_info.get("uid"),
                    "sec_uid": user_info.get("sec_uid"),
                    "short_user_id": user_info.get("short_id"),
                    "user_unique_id": user_info.get("unique_id"),
                    "nickname": user_info.get("nickname"),
                    "avatar": user_info.get("avatar_thumb", {}).get("url_list", [""])[0],
                    "liked_count": str(interact_info.get("digg_count", 0)),
                    "collected_count": str(interact_info.get("collect_count", 0)),
                    "comment_count": str(interact_info.get("comment_count", 0)),
                    "share_count": str(interact_info.get("share_count", 0)),
                    "ip_location": aweme_info.get("ip_label", ""),
                    "aweme_url": f"https://www.douyin.com/video/{aweme_info.get('aweme_id')}",
                }
                batch_videos.append(aweme_data)

            if not batch_videos:
                break

            remaining_slots = max_videos - len(all_videos)
            if remaining_slots <= 0:
                break

            if len(batch_videos) > remaining_slots:
                batch_videos = batch_videos[:remaining_slots]

            all_videos.extend(batch_videos)
            logger.info(f"Fetched {len(batch_videos)} videos for user {sec_user_id}, total: {len(all_videos)}")

            await asyncio.sleep(1.0)  # Rate limiting

        return all_videos

    async def check_login_status(self) -> bool:
        """
        Check if user is logged in to Douyin
        
        Returns:
            True if logged in, False otherwise
        """
        try:
            if not self.target_id:
                return False

            cdp_session = await self.browser_session.get_or_create_cdp_session(target_id=self.target_id)

            # Check localStorage for login status
            result = await cdp_session.cdp_client.send.Runtime.evaluate(
                params={
                    'expression': "window.localStorage.getItem('HasUserLogin')",
                    'returnByValue': True,
                },
                session_id=cdp_session.session_id,
            )

            has_user_login = result.get('result', {}).get('value')
            if has_user_login == "1":
                return True

            # Also check cookies for LOGIN_STATUS
            return self.cookies.get("LOGIN_STATUS") == "1"

        except Exception as e:
            logger.error(f"Failed to check login status: {e}")
            return False

    async def close(self):
        if self.browser_session and self.target_id and self.new_tab:
            try:
                logger.info(f"Close target id: {self.target_id}")
                await self.browser_session.cdp_client.send.Target.closeTarget(params={'targetId': self.target_id})
            except Exception as e:
                logger.warning(f"Error closing target {self.target_id}: {e}")

