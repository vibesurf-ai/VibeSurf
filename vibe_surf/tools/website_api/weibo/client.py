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
            if target_id:
                self.target_id = target_id
            else:
                # Navigate to mobile version for better API compatibility
                self.target_id = await self.browser_session.navigate_to_url(
                    "https://weibo.com/", new_tab=True
                )
                await asyncio.sleep(3)  # Wait for page load

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

            # Check if user is logged in
            is_logged_in = await self.pong()

            if not is_logged_in:
                logger.warning("User is not logged in to Weibo, redirecting to login page")
                
                # Navigate to Weibo SSO login page
                weibo_sso_login_url = "https://passport.weibo.com/sso/signin?entry=miniblog&source=miniblog"
                await self.browser_session.navigate_to_url(weibo_sso_login_url, new_tab=True)

                # Raise authentication error to inform user they need to login
                raise AuthenticationError("User is not logged in to Weibo. Please complete login process and try again.")

            logger.info("Weibo client setup completed successfully")

        except AuthenticationError:
            # Re-raise authentication errors as-is
            raise
        except Exception as e:
            logger.error(f"Failed to setup Weibo client: {e}")
            raise AuthenticationError(f"Setup failed: {e}")


    async def pong(self) -> bool:
        """Check if login state is valid using multiple methods"""
        try:
            logger.info("Testing Weibo login status...")

            # Method 1: Check essential login cookies
            login_cookies = ['SUB', 'SUBP', 'ALF', 'SSOLoginState']
            has_essential_cookies = any(
                cookie_name in self.cookies and self.cookies[cookie_name]
                for cookie_name in login_cookies
            )
            if has_essential_cookies:
                logger.info("Weibo login status: Valid (found essential cookies)")
                return True

            # Method 2: Try to access user info API
            try:
                uri = "/api/config"
                response_data = await self._make_request("GET", f"{self._api_base}{uri}")

                if isinstance(response_data, dict) and response_data.get("login"):
                    logger.info("Weibo login status: Valid (API check passed)")
                    return True
            except Exception as api_error:
                logger.debug(f"API config check failed: {api_error}")

            # Method 3: Check browser localStorage for login indicators
            try:
                cdp_session = await self.browser_session.get_or_create_cdp_session(target_id=self.target_id)
                js_check = """
                (function() {
                    try {
                        // Check various login indicators
                        var hasLoginCookie = document.cookie.includes('SUB=') || document.cookie.includes('SUBP=');
                        var hasLoginStorage = localStorage.getItem('login_status') === '1' ||
                                            localStorage.getItem('isLogin') === 'true' ||
                                            localStorage.getItem('weiboLoginStatus') === '1';
                        
                        // Check if there's user info in the page
                        var hasUserInfo = window.__INITIAL_STATE__ &&
                                         window.__INITIAL_STATE__.user &&
                                         window.__INITIAL_STATE__.user.id;
                        
                        return hasLoginCookie || hasLoginStorage || hasUserInfo;
                    } catch(e) {
                        return false;
                    }
                })()
                """

                result = await cdp_session.cdp_client.send.Runtime.evaluate(
                    params={
                        'expression': js_check,
                        'returnByValue': True,
                    },
                    session_id=cdp_session.session_id,
                )

                browser_login_check = result.get('result', {}).get('value', False)
                if browser_login_check:
                    logger.info("Weibo login status: Valid (browser check passed)")
                    return True

            except Exception as browser_error:
                logger.debug(f"Browser login check failed: {browser_error}")

            logger.warning("Weibo login status: No valid login indicators found")
            return False

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
        if response.status_code == 302:
            logger.warning(f"302 redirect detected for {url}, final URL: {response.url}")
            # Don't raise error for 302, let it follow redirects and check final response
        elif response.status_code == 403:
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

    async def _get_request(self, endpoint: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Dict:
        """Make GET request with proper headers and parameters"""
        final_endpoint = endpoint
        if params:
            final_endpoint = f"{endpoint}?{urllib.parse.urlencode(params)}"
        
        request_headers = headers or self.default_headers
        
        return await self._make_request(
            "GET", f"{self._api_base}{final_endpoint}",
            headers=request_headers
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
    ) -> Dict:
        """
        Search Weibo posts by keyword
        
        Args:
            keyword: Search keyword
            page: Page number (starting from 1)
            search_type: Search type filter
            
        Returns:
            Search results containing posts
        """
        endpoint = "/api/container/getIndex"
        container_id = create_container_id(search_type, keyword)
        
        params = {
            "containerid": container_id,
            "page_type": "searchall",
            "page": str(page),
        }
        
        return await self._get_request(endpoint, params)

    async def get_post_detail(self, mid_id: str) -> Dict:
        """
        Get detailed post information by mid ID
        
        Args:
            mid_id: Weibo post ID
            
        Returns:
            Post detail information
        """
        url = f"{self._api_base}/detail/{mid_id}"

        response = await self._make_request(
            "GET", url, headers=self.default_headers, raw_response=True,
        )
        # Extract render data from HTML
        render_data = extract_render_data(response.text)
        if render_data:
            note_detail = render_data.get("status")
            if note_detail:
                return {"mblog": note_detail}
        
        logger.warning(f"Could not extract render data for post {mid_id}")
        return {}

    async def get_post_comments(
        self, 
        mid_id: str, 
        max_id: int = 0, 
        max_id_type: int = 0
    ) -> Dict:
        """
        Get comments for a Weibo post
        
        Args:
            mid_id: Weibo post ID
            max_id: Pagination parameter
            max_id_type: Pagination type parameter
            
        Returns:
            Comments data
        """
        endpoint = "/comments/hotflow"
        
        params = {
            "id": mid_id,
            "mid": mid_id,
            "max_id_type": str(max_id_type),
        }
        
        if max_id > 0:
            params["max_id"] = str(max_id)
        
        # Set referer for comment requests
        headers = copy.deepcopy(self.default_headers)
        headers["Referer"] = f"https://m.weibo.cn/detail/{mid_id}"
        
        return await self._get_request(endpoint, params, headers)

    async def get_all_post_comments(
        self,
        post_id: str,
        fetch_interval: float = 1.0,
        include_sub_comments: bool = False,
        progress_callback: Optional[Callable] = None,
        max_comments: int = 1000,
    ) -> List[Dict]:
        """
        Fetch all comments for a post including sub-comments
        
        Args:
            post_id: Weibo post ID
            fetch_interval: Interval between requests in seconds
            include_sub_comments: Whether to include sub-comments
            progress_callback: Callback function for progress updates
            max_comments: Maximum comments to fetch
            
        Returns:
            List of all comments
        """
        all_comments = []
        is_end = False
        max_id = -1
        max_id_type = 0

        while not is_end and len(all_comments) < max_comments:
            comments_data = await self.get_post_comments(post_id, max_id, max_id_type)
            
            max_id = comments_data.get("max_id", 0)
            max_id_type = comments_data.get("max_id_type", 0)
            comment_list = comments_data.get("data", [])
            is_end = max_id == 0
            
            # Limit comments if approaching max
            remaining_slots = max_comments - len(all_comments)
            if len(comment_list) > remaining_slots:
                comment_list = comment_list[:remaining_slots]
            
            if progress_callback:
                await progress_callback(post_id, comment_list)
            
            await asyncio.sleep(fetch_interval)
            all_comments.extend(comment_list)
            
            # Extract sub-comments if enabled
            if include_sub_comments:
                sub_comments = await self._extract_sub_comments(
                    post_id, comment_list, progress_callback
                )
                all_comments.extend(sub_comments)

        logger.info(f"Fetched {len(all_comments)} comments for post {post_id}")
        return all_comments

    async def _extract_sub_comments(
        self,
        post_id: str,
        comment_list: List[Dict],
        progress_callback: Optional[Callable] = None,
    ) -> List[Dict]:
        """Extract sub-comments from comment list"""
        sub_comments = []
        
        for comment in comment_list:
            comments_data = comment.get("comments")
            if comments_data and isinstance(comments_data, list):
                if progress_callback:
                    await progress_callback(post_id, comments_data)
                sub_comments.extend(comments_data)
                
        return sub_comments

    async def get_user_container_info(self, user_id: str) -> Dict:
        """
        Get user container information for API requests
        
        Args:
            user_id: User ID
            
        Returns:
            Container information with fid and lfid
        """
        # Use the correct mobile API endpoint for user profile
        headers = copy.deepcopy(self.default_headers)
        headers["Referer"] = f"{self._api_base}/u/{user_id}"
        
        response = await self._make_request(
            "GET", f"{self._api_base}/api/container/getIndex",
            params={
                "type": "uid",
                "value": user_id,
                "containerid": f"100505{user_id}"  # Standard user profile container ID
            },
            headers=headers, raw_response=True
        )
        
        # Extract container info from cookies if available
        m_weibocn_params = None
        for cookie in response.cookies:
            if cookie.name == "M_WEIBOCN_PARAMS":
                m_weibocn_params = cookie.value
                break
        
        if m_weibocn_params:
            return extract_container_params(m_weibocn_params)
        else:
            # Fallback to standard container IDs
            return {
                "fid_container_id": f"100505{user_id}",
                "lfid_container_id": f"100505{user_id}"
            }

    async def get_user_info(self, user_id: str) -> Dict:
        """
        Get user profile information
        
        Args:
            user_id: User ID
            
        Returns:
            User profile data with container information
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
            if "cards" in user_data and user_data["cards"]:
                # Look for user card in the response
                for card in user_data["cards"]:
                    if card.get("card_type") == 10:  # User info card type
                        user_info = card.get("user", {})
                        if user_info:
                            return {
                                "user": user_info,
                                "containerid": f"100505{user_id}",
                                "tabsInfo": user_data.get("tabsInfo", {})
                            }
            
            # Fallback: try to get user info from the first available card
            if "cards" in user_data and user_data["cards"]:
                first_card = user_data["cards"][0]
                if "user" in first_card:
                    return {
                        "user": first_card["user"],
                        "containerid": f"100505{user_id}",
                        "tabsInfo": user_data.get("tabsInfo", {})
                    }
            
            # If no user data found, return basic structure
            return {
                "user": {"id": user_id},
                "containerid": f"100505{user_id}",
                "tabsInfo": user_data.get("tabsInfo", {})
            }
            
        except Exception as e:
            logger.error(f"Failed to get user info for {user_id}: {e}")
            # Try alternative approach using direct API call
            try:
                alt_params = {
                    "containerid": f"230283{user_id}",  # Alternative container ID
                    "featurecode": "20000320",
                    "lfid": f"100505{user_id}",
                    "uid": user_id
                }
                alt_data = await self._get_request(endpoint, alt_params, headers)
                return alt_data
            except Exception as alt_e:
                logger.error(f"Alternative user info request also failed: {alt_e}")
                raise DataExtractionError(f"Failed to get user info for {user_id}: {e}")

    async def get_user_posts(
        self,
        user_id: str,
        container_id: str,
        since_id: str = "0",
    ) -> Dict:
        """
        Get posts by user
        
        Args:
            user_id: User ID
            container_id: Container ID for the user
            since_id: Pagination parameter (last post ID from previous page)
            
        Returns:
            User posts data
        """
        endpoint = "/api/container/getIndex"
        
        params = {
            "jumpfrom": "weibocom",
            "type": "uid",
            "value": user_id,
            "containerid": container_id,
            "since_id": since_id,
        }
        
        return await self._get_request(endpoint, params)

    async def get_all_user_posts(
        self,
        user_id: str,
        container_id: str,
        fetch_interval: float = 1.0,
        progress_callback: Optional[Callable] = None,
        max_posts: int = 1000,
    ) -> List[Dict]:
        """
        Fetch all posts by a user
        
        Args:
            user_id: User ID
            container_id: Container ID for the user
            fetch_interval: Interval between requests in seconds
            progress_callback: Callback function for progress updates
            max_posts: Maximum posts to fetch
            
        Returns:
            List of all user posts
        """
        all_posts = []
        has_more = True
        since_id = ""
        crawler_total_count = 0

        while has_more and len(all_posts) < max_posts:
            posts_data = await self.get_user_posts(user_id, container_id, since_id)
            
            if not posts_data:
                logger.error(f"User {user_id} may be restricted or data unavailable")
                break
            
            since_id = posts_data.get("cardlistInfo", {}).get("since_id", "0")
            
            if "cards" not in posts_data:
                logger.info(f"No posts found in response for user {user_id}")
                break
            
            posts = posts_data["cards"]
            # Filter only card_type=9 (actual posts)
            posts = [post for post in posts if post.get("card_type") == 9]
            
            logger.info(f"Fetched {len(posts)} posts for user {user_id}")
            
            remaining_slots = max_posts - len(all_posts)
            if remaining_slots <= 0:
                break
                
            posts_to_add = posts[:remaining_slots]
            
            if progress_callback:
                await progress_callback(posts_to_add)
            
            all_posts.extend(posts_to_add)
            await asyncio.sleep(fetch_interval)
            
            crawler_total_count += 10
            total_available = posts_data.get("cardlistInfo", {}).get("total", 0)
            has_more = total_available > crawler_total_count

        logger.info(f"Fetched total {len(all_posts)} posts for user {user_id}")
        return all_posts

    async def extract_post_info(self, post_data: Dict) -> Dict:
        """
        Extract useful information from Weibo post data
        
        Args:
            post_data: Raw post data from API
            
        Returns:
            Processed post information
        """
        mblog = post_data.get("mblog", {})
        
        if not validate_weibo_data(mblog):
            raise DataExtractionError("Invalid Weibo post data structure")
        
        try:
            user = mblog.get("user", {})
            
            post_info = {
                "mid": mblog.get("id"),
                "text": process_weibo_text(mblog.get("text", "")),
                "created_at": mblog.get("created_at"),
                "source": mblog.get("source"),
                "reposts_count": mblog.get("reposts_count", 0),
                "comments_count": mblog.get("comments_count", 0),
                "attitudes_count": mblog.get("attitudes_count", 0),
                "user": {
                    "id": user.get("id"),
                    "screen_name": user.get("screen_name"),
                    "profile_image_url": user.get("profile_image_url"),
                    "followers_count": user.get("followers_count", 0),
                    "friends_count": user.get("friends_count", 0),
                    "statuses_count": user.get("statuses_count", 0),
                },
                "pics": mblog.get("pics", []),
                "page_info": mblog.get("page_info", {}),  # Video info if present
            }
            
            return post_info
            
        except Exception as e:
            logger.error(f"Failed to extract post info: {e}")
            raise DataExtractionError(f"Failed to process post data: {e}")

    async def get_trending_list(self) -> Dict:
        """
        Get Weibo trending list (热搜榜)
        
        Returns:
            Trending list data containing hot topics
        """
        endpoint = "/api/feed/trendtop"
        params = {
            "containerid": TrendingConstants.TRENDING_CONTAINER_ID
        }
        
        return await self._get_request(endpoint, params)

    async def get_hot_posts(self) -> Dict:
        """
        Get Weibo hot posts (热门推荐)
        
        Returns:
            Hot posts data containing recommended content
        """
        endpoint = "/api/container/getIndex"
        params = {
            "containerid": TrendingConstants.HOT_POSTS_CONTAINER_ID,
            "openApp": TrendingConstants.OPEN_APP
        }
        
        return await self._get_request(endpoint, params)