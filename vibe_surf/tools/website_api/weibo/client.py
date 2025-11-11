import asyncio
import json
import pdb
import re
import copy
import time
import urllib.parse
from typing import Dict, List, Optional, Callable, Union, Any
import httpx
from tenacity import retry, stop_after_attempt, wait_fixed
from urllib.parse import parse_qs, unquote, urlencode

from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.logger import get_logger

from .helpers import (
    SearchType, TrendingType, TrendingConstants,
    create_container_id, extract_cookies_from_browser,
    filter_search_result_card, extract_container_params,
    build_image_proxy_url, extract_render_data, process_weibo_text,
    validate_weibo_data, sanitize_filename,
    extract_redirect_url_from_html, decode_chinese_html,
    WeiboError, NetworkError, DataExtractionError,
    AuthenticationError, RateLimitError, ContentNotFoundError,
    get_mobile_user_agent
)

logger = get_logger(__name__)


class WeiboApiClient:
    """
    Weibo API client with integrated browser session management.
    This client handles API communication through browser session for authentication.
    """

    def __init__(self, browser_session: AgentBrowserSession, timeout: int = 60, proxy: Optional[str] = None):
        """
        Initialize the Weibo API client
        
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
        self._api_base = "https://m.weibo.cn"
        self._web_base = "https://www.weibo.com"
        self._image_proxy_host = "https://i1.wp.com/"

        # Default headers for mobile Weibo
        self.default_headers = {
            "User-Agent": get_mobile_user_agent(),
            "Origin": "https://m.weibo.cn",
            "Referer": "https://m.weibo.cn",
            "Content-Type": "application/json;charset=UTF-8",
        }
        self.cookies = {}

    async def setup(self, target_id: Optional[str] = None):
        """
        Setup Weibo client by navigating to the site and extracting cookies
        
        Args:
            target_id: Specific browser target ID to use
            
        Raises:
            AuthenticationError: If setup fails or user is not logged in
        """
        try:
            if self.target_id and self.cookies:
                logger.info("Already setup. Return!")
                return
            if target_id:
                self.target_id = target_id
            else:
                # Navigate to mobile version for better API compatibility
                self.target_id = await self.browser_session.navigate_to_url(
                    "https://weibo.com/", new_tab=True
                )
                self.new_tab = True
                await asyncio.sleep(2)  # Wait for page load

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

            is_logged_in = await self.check_login()

            if not is_logged_in:
                self.cookies = {}
                del self.default_headers["Cookie"]
                raise AuthenticationError(f"Please login in [微博]({self._web_base}) first!")

            logger.info("Weibo client setup completed successfully")

        except Exception as e:
            logger.error(f"Failed to setup Weibo client: {e}")
            raise AuthenticationError(f"Setup failed: {e}")

    async def check_login(self) -> bool:
        """Check if login state is valid using multiple methods"""
        try:
            ret = await self.search_posts_by_keyword("小红书")
            return ret and len(ret) > 0
        except Exception as e:
            logger.error(f"Failed to check Weibo login status: {e}")
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
            data = response.json()

            # Check Weibo API response format
            if isinstance(data, dict):
                ok_code = data.get("ok")
                if ok_code == 0:  # Weibo error response
                    error_msg = data.get("msg", "Response error")
                    logger.error(f"Weibo API error: {error_msg}")
                    raise DataExtractionError(error_msg)
                elif ok_code == 1:  # Success response
                    return data.get("data", {})
                elif ok_code is None:  # Some endpoints don't return 'ok' field
                    return data
                else:  # Unknown error
                    error_msg = data.get("msg", "Unknown error")
                    logger.error(f"Weibo API unknown error: {error_msg}")
                    raise DataExtractionError(error_msg)

            return data

        except json.JSONDecodeError:
            raise DataExtractionError(f"Invalid JSON response: {response.text[:200]}")

    async def _get_request(self, endpoint: str, params: Optional[Dict] = None, headers: Optional[Dict] = None,
                           **kwargs) -> Dict:
        """Make GET request with proper headers and parameters"""
        final_endpoint = endpoint
        if params:
            final_endpoint = f"{endpoint}?{urllib.parse.urlencode(params)}"

        request_headers = headers or self.default_headers

        return await self._make_request(
            "GET", f"{self._api_base}{final_endpoint}",
            headers=request_headers,
            **kwargs
        )

    async def _post_request(self, endpoint: str, data: Dict, headers: Optional[Dict] = None) -> Dict:
        """Make POST request with proper headers and data"""
        request_headers = headers or self.default_headers
        json_payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)

        return await self._make_request(
            "POST", f"{self._api_base}{endpoint}",
            data=json_payload, headers=request_headers
        )

    async def search_posts_by_keyword(
            self,
            keyword: str,
            page: int = 1,
            search_type: SearchType = SearchType.DEFAULT,
    ) -> List[Dict]:
        """
        Search Weibo posts by keyword
        
        Args:
            keyword: Search keyword
            page: Page number (starting from 1)
            search_type: Search type filter
            
        Returns:
            List of simplified post information
        """
        endpoint = "/api/container/getIndex"
        container_id = create_container_id(search_type, keyword)

        cards = []
        posts = []
        for page_num in range(page):
            params = {
                "containerid": container_id,
                "page_type": "searchall",
                "page": page_num,
            }

            raw_response = await self._get_request(endpoint, params)
            cards.extend(raw_response.get("cards", []))

        for card in cards:
            mblog = card.get("mblog", {})
            if not mblog.get("id"):
                continue

            user_info = mblog.get("user", {})
            clean_text = re.sub(r"<.*?>", "", mblog.get("text", ""))

            post = {
                "note_id": mblog.get("id"),
                "content": clean_text,
                "created_at": mblog.get("created_at"),
                "liked_count": str(mblog.get("attitudes_count", 0)),
                "comments_count": str(mblog.get("comments_count", 0)),
                "shared_count": str(mblog.get("reposts_count", 0)),
                "ip_location": mblog.get("region_name", "").replace("发布于 ", ""),
                "note_url": f"https://m.weibo.cn/detail/{mblog.get('id')}",
                "user_id": str(user_info.get("id", "")),
                "nickname": user_info.get("screen_name", ""),
                "gender": user_info.get("gender", ""),
                "profile_url": user_info.get("profile_url", ""),
                "avatar": user_info.get("profile_image_url", ""),
            }
            posts.append(post)

        return posts

    async def get_post_detail(self, mid: str) -> Optional[Dict]:
        """
        Get detailed post information by mid ID
        
        Args:
            mid: Weibo post ID
            
        Returns:
            Simplified post detail information
        """
        url = f"{self._api_base}/detail/{mid}"

        response = await self._make_request(
            "GET", url, headers=self.default_headers, raw_response=True,
        )
        # Extract render data from HTML
        render_data = extract_render_data(response.text)
        if render_data:
            note_detail = render_data.get("status")
            if note_detail:
                user_info = note_detail.get("user", {})
                clean_text = re.sub(r"<.*?>", "", note_detail.get("text", ""))

                return {
                    "note_id": note_detail.get("id"),
                    "content": clean_text,
                    "created_at": note_detail.get("created_at"),
                    "liked_count": str(note_detail.get("attitudes_count", 0)),
                    "comments_count": str(note_detail.get("comments_count", 0)),
                    "shared_count": str(note_detail.get("reposts_count", 0)),
                    "ip_location": note_detail.get("region_name", "").replace("发布于 ", ""),
                    "note_url": f"https://m.weibo.cn/detail/{note_detail.get('id')}",
                    "user_id": str(user_info.get("id", "")),
                    "nickname": user_info.get("screen_name", ""),
                    "gender": user_info.get("gender", ""),
                    "profile_url": user_info.get("profile_url", ""),
                    "avatar": user_info.get("profile_image_url", ""),
                }

        logger.warning(f"Could not extract render data for post {mid}")
        return None

    async def get_post_comments(
            self,
            mid: str,
            max_id: int = 0,
            max_id_type: int = 0
    ) -> List[Dict]:
        """
        Get comments for a Weibo post
        
        Args:
            mid: Weibo post ID
            max_id: Pagination parameter
            max_id_type: Pagination type parameter
            
        Returns:
            List of simplified comment information
        """
        endpoint = "/comments/hotflow"

        params = {
            "id": mid,
            "mid": mid,
            "max_id_type": str(max_id_type),
        }

        if max_id > 0:
            params["max_id"] = str(max_id)

        # Set referer for comment requests
        headers = copy.deepcopy(self.default_headers)
        headers["Referer"] = f"https://m.weibo.cn/detail/{mid}"

        raw_response = await self._get_request(endpoint, params, headers)

        # Return simplified comments
        comments = []
        for comment in raw_response.get("data", []):
            if not comment.get("id"):
                continue

            user_info = comment.get("user", {})
            clean_text = re.sub(r"<.*?>", "", comment.get("text", ""))

            comment_data = {
                "comment_id": str(comment.get("id")),
                "content": clean_text,
                "created_at": comment.get("created_at"),
                "comment_like_count": str(comment.get("like_count", 0)),
                "sub_comment_count": str(comment.get("total_number", 0)),
                "ip_location": comment.get("source", "").replace("来自", ""),
                "parent_comment_id": comment.get("rootid", ""),
                "user_id": str(user_info.get("id", "")),
                "nickname": user_info.get("screen_name", ""),
                "gender": user_info.get("gender", ""),
                "profile_url": user_info.get("profile_url", ""),
                "avatar": user_info.get("profile_image_url", ""),
            }
            comments.append(comment_data)

        return comments

    async def get_all_post_comments(
            self,
            mid: str,
            fetch_interval: float = 1.0,
            include_sub_comments: bool = False,
            max_comments: int = 1000,
    ) -> List[Dict]:
        """
        Fetch all comments for a post including sub-comments
        
        Args:
            mid: Weibo post ID
            fetch_interval: Interval between requests in seconds
            include_sub_comments: Whether to include sub-comments
            max_comments: Maximum comments to fetch
            
        Returns:
            List of all simplified comments
        """
        all_comments = []
        is_end = False
        max_id = -1
        max_id_type = 0

        while not is_end and len(all_comments) < max_comments:
            # Get raw response to access pagination info
            endpoint = "/comments/hotflow"

            params = {
                "id": mid,
                "mid": mid,
                "max_id_type": str(max_id_type),
            }

            if max_id > 0:
                params["max_id"] = str(max_id)

            # Set referer for comment requests
            headers = copy.deepcopy(self.default_headers)
            headers["Referer"] = f"https://m.weibo.cn/detail/{mid}"

            raw_response = await self._get_request(endpoint, params, headers)

            # Extract pagination info from raw response
            max_id = raw_response.get("max_id", 0)
            max_id_type = raw_response.get("max_id_type", 0)
            is_end = max_id == 0

            # Transform to simplified comments
            batch_comments = []
            for comment in raw_response.get("data", []):
                if not comment.get("id"):
                    continue

                user_info = comment.get("user", {})
                clean_text = re.sub(r"<.*?>", "", comment.get("text", ""))

                comment_data = {
                    "comment_id": str(comment.get("id")),
                    "content": clean_text,
                    "created_at": comment.get("created_at"),
                    "comment_like_count": str(comment.get("like_count", 0)),
                    "sub_comment_count": str(comment.get("total_number", 0)),
                    "ip_location": comment.get("source", "").replace("来自", ""),
                    "parent_comment_id": comment.get("rootid", ""),
                    "user_id": str(user_info.get("id", "")),
                    "nickname": user_info.get("screen_name", ""),
                    "gender": user_info.get("gender", ""),
                    "profile_url": user_info.get("profile_url", ""),
                    "avatar": user_info.get("profile_image_url", ""),
                }
                batch_comments.append(comment_data)

            # Limit comments if approaching max
            remaining_slots = max_comments - len(all_comments)
            if len(batch_comments) > remaining_slots:
                batch_comments = batch_comments[:remaining_slots]

            await asyncio.sleep(fetch_interval)
            all_comments.extend(batch_comments)

        logger.info(f"Fetched {len(all_comments)} comments for post {mid}")
        return all_comments

    async def get_user_info(self, user_id: str) -> Optional[Dict]:
        """
        Get user profile information
        
        Args:
            user_id: User ID
            
        Returns:
            Simplified user profile information
        """
        endpoint = "/api/container/getIndex"

        # Set proper headers for user info request
        headers = copy.deepcopy(self.default_headers)
        headers["Referer"] = f"{self._api_base}/u/{user_id}"

        # Use standard user profile container ID
        params = {
            "type": "uid",
            "value": user_id,
            "containerid": f"100505{user_id}",  # Standard user profile container
        }

        try:
            user_data = await self._get_request(endpoint, params, headers)
            # Extract user info from cards if available
            user_info = user_data.get('userInfo', {})
            user_info["user_id"] = user_info.get("id", user_id)
            return user_info

        except Exception as e:
            logger.error(f"Failed to get user info for {user_id}: {e}")
            return None

    async def get_user_posts(
            self,
            user_id: str,
            since_id: str = "0",
    ) -> Optional[Dict]:
        """
        Get posts by user
        
        Args:
            user_id: User ID
            since_id: Pagination parameter (last post ID from previous page)
            
        Returns:
            Simplified user posts data
        """
        endpoint = "/api/container/getIndex"

        # response = await self._get_request(f"/u/{user_id}", raw_response=True)
        # m_weibocn_params = response.cookies.get("M_WEIBOCN_PARAMS")
        # m_weibocn_params_dict = parse_qs(unquote(m_weibocn_params))
        # containerid = m_weibocn_params_dict['fid'][0]

        params = {
            "jumpfrom": "weibocom",
            "type": "uid",
            "value": user_id,
            "containerid": f"100505{user_id}",
            "since_id": since_id,
        }

        response = await self._get_request(endpoint, params)
        containerid = f"100505{user_id}"
        if response.get("tabsInfo"):
            tabs: List[Dict] = response.get("tabsInfo", {}).get("tabs", [])
            for tab in tabs:
                if tab.get("tabKey") == "weibo":
                    containerid = tab.get("containerid")
                    break
        params = {
            "jumpfrom": "weibocom",
            "type": "uid",
            "value": user_id,
            "containerid": containerid,
            "since_id": since_id,
        }

        response = await self._get_request(endpoint, params)

        # Transform to simplified posts
        posts = []
        cards = response.get("cards", [])
        for card in cards:
            if card.get("card_type") == 9:  # Weibo post card type
                mblog = card.get("mblog", {})
                if not mblog.get("id"):
                    continue

                user_info = mblog.get("user", {})
                clean_text = re.sub(r"<.*?>", "", mblog.get("text", ""))

                post = {
                    "note_id": mblog.get("id"),
                    "content": clean_text,
                    "created_at": mblog.get("created_at"),
                    "liked_count": str(mblog.get("attitudes_count", 0)),
                    "comments_count": str(mblog.get("comments_count", 0)),
                    "shared_count": str(mblog.get("reposts_count", 0)),
                    "ip_location": mblog.get("region_name", "").replace("发布于 ", ""),
                    "note_url": f"https://m.weibo.cn/detail/{mblog.get('id')}",
                    "user_id": str(user_info.get("id", "")),
                    "nickname": user_info.get("screen_name", ""),
                    "gender": user_info.get("gender", ""),
                    "profile_url": user_info.get("profile_url", ""),
                    "avatar": user_info.get("profile_image_url", ""),
                }
                posts.append(post)

        return {
            "posts": posts,
            "pagination": {
                "since_id": response.get("cardlistInfo", {}).get("since_id", ""),
                "total": response.get("cardlistInfo", {}).get("total", 0)
            }
        }

    async def get_all_user_posts(
            self,
            user_id: str,
            fetch_interval: float = 1.0,
            max_posts: int = 1000,
    ) -> List[Dict]:
        """
        Fetch all posts by a user
        
        Args:
            user_id: User ID
            fetch_interval: Interval between requests in seconds
            max_posts: Maximum posts to fetch
            
        Returns:
            List of all simplified user posts
        """
        all_posts = []
        has_more = True
        since_id = ""
        crawler_total_count = 0

        while has_more and len(all_posts) < max_posts:
            # Get raw response to access pagination info and then transform
            endpoint = "/api/container/getIndex"

            params = {
                "jumpfrom": "weibocom",
                "type": "uid",
                "value": user_id,
                "containerid": f"100505{user_id}",
                "since_id": since_id,
            }

            raw_posts_data = await self._get_request(endpoint, params)

            if not raw_posts_data:
                logger.error(f"User {user_id} may be restricted or data unavailable")
                break

            # Extract pagination info from raw response
            since_id = raw_posts_data.get("cardlistInfo", {}).get("since_id", "0")
            if "cards" not in raw_posts_data:
                logger.info(f"No posts found in response for user {user_id}")
                break

            # Transform to simplified posts
            posts = []
            cards = raw_posts_data.get("cards", [])
            for card in cards:
                if card.get("card_type") == 9:  # Weibo post card type
                    mblog = card.get("mblog", {})
                    if not mblog.get("id"):
                        continue

                    user_info = mblog.get("user", {})
                    clean_text = re.sub(r"<.*?>", "", mblog.get("text", ""))

                    post = {
                        "note_id": mblog.get("id"),
                        "content": clean_text,
                        "created_at": mblog.get("created_at"),
                        "liked_count": str(mblog.get("attitudes_count", 0)),
                        "comments_count": str(mblog.get("comments_count", 0)),
                        "shared_count": str(mblog.get("reposts_count", 0)),
                        "ip_location": mblog.get("region_name", "").replace("发布于 ", ""),
                        "note_url": f"https://m.weibo.cn/detail/{mblog.get('id')}",
                        "user_id": str(user_info.get("id", "")),
                        "nickname": user_info.get("screen_name", ""),
                        "gender": user_info.get("gender", ""),
                        "profile_url": user_info.get("profile_url", ""),
                        "avatar": user_info.get("profile_image_url", ""),
                    }
                    posts.append(post)

            logger.info(f"Fetched {len(posts)} posts for user {user_id}")

            remaining_slots = max_posts - len(all_posts)
            if remaining_slots <= 0:
                break

            posts_to_add = posts[:remaining_slots]

            all_posts.extend(posts_to_add)
            await asyncio.sleep(fetch_interval)

            crawler_total_count += 10
            total_available = raw_posts_data.get("cardlistInfo", {}).get("total", 0)
            has_more = total_available > crawler_total_count and since_id != "0"

        logger.info(f"Fetched total {len(all_posts)} posts for user {user_id}")
        return all_posts

    async def get_trending_posts(self) -> List[Dict]:
        """
        Get Weibo trending posts (热搜榜)
        
        Returns:
            List of simplified trending post information
        """
        endpoint = "/api/feed/trendtop"
        params = {
            "containerid": TrendingConstants.TRENDING_CONTAINER_ID
        }

        raw_response = await self._get_request(endpoint, params)

        # Transform to simplified posts
        posts = []
        cards = raw_response.get("statuses", [])
        for mblog in cards:
            if not mblog.get("id"):
                continue

            user_info = mblog.get("user", {})
            clean_text = re.sub(r"<.*?>", "", mblog.get("text", ""))

            post = {
                "note_id": mblog.get("id"),
                "content": clean_text,
                "created_at": mblog.get("created_at"),
                "liked_count": str(mblog.get("attitudes_count", 0)),
                "comments_count": str(mblog.get("comments_count", 0)),
                "shared_count": str(mblog.get("reposts_count", 0)),
                "ip_location": mblog.get("region_name", "").replace("发布于 ", ""),
                "note_url": f"https://m.weibo.cn/detail/{mblog.get('id')}",
                "user_id": str(user_info.get("id", "")),
                "nickname": user_info.get("screen_name", ""),
                "gender": user_info.get("gender", ""),
                "profile_url": user_info.get("profile_url", ""),
                "avatar": user_info.get("profile_image_url", ""),
            }
            posts.append(post)

        return posts

    async def get_hot_posts(self) -> List[Dict]:
        """
        Get Weibo hot posts (热门推荐)
        
        Returns:
            List of simplified hot post information
        """
        endpoint = "/api/container/getIndex"
        params = {
            "containerid": TrendingConstants.HOT_POSTS_CONTAINER_ID,
            "openApp": TrendingConstants.OPEN_APP
        }

        raw_response = await self._get_request(endpoint, params)

        # Transform to simplified posts (same structure as search results)
        posts = []
        cards = raw_response.get("cards", [])
        for card in cards:
            if card.get("card_type") == 9:  # Weibo post card type
                mblog = card.get("mblog", {})
                if not mblog.get("id"):
                    continue

                user_info = mblog.get("user", {})
                clean_text = re.sub(r"<.*?>", "", mblog.get("text", ""))

                post = {
                    "note_id": mblog.get("id"),
                    "content": clean_text,
                    "created_at": mblog.get("created_at"),
                    "liked_count": str(mblog.get("attitudes_count", 0)),
                    "comments_count": str(mblog.get("comments_count", 0)),
                    "shared_count": str(mblog.get("reposts_count", 0)),
                    "ip_location": mblog.get("region_name", "").replace("发布于 ", ""),
                    "note_url": f"https://m.weibo.cn/detail/{mblog.get('id')}",
                    "user_id": str(user_info.get("id", "")),
                    "nickname": user_info.get("screen_name", ""),
                    "gender": user_info.get("gender", ""),
                    "profile_url": user_info.get("profile_url", ""),
                    "avatar": user_info.get("profile_image_url", ""),
                }
                posts.append(post)

        return posts

    async def close(self):
        if self.browser_session and self.target_id and self.new_tab:
            try:
                logger.info(f"Close target id: {self.target_id}")
                await self.browser_session.cdp_client.send.Target.closeTarget(params={'targetId': self.target_id})
            except Exception as e:
                logger.warning(f"Error closing target {self.target_id}: {e}")

