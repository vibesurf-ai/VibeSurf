import asyncio
import json
import pdb
import time
from typing import Dict, List, Optional, Callable, Union, Any
import httpx
from urllib.parse import urlencode
import random
import copy
from tenacity import retry, stop_after_attempt, wait_fixed

from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.logger import get_logger

from .helpers import (
    generate_trace_id, create_session_id, create_signature_headers,
    extract_cookies_from_browser, XHSError, NetworkError,
    DataExtractionError, AuthenticationError
)

logger = get_logger(__name__)


class SearchType:
    """Search type constants"""
    GENERAL = "general"
    LATEST = "time"
    POPULAR = "popularity_descending"


class ContentType:
    """Content type constants"""
    ALL = 0
    VIDEO = 1
    IMAGE = 2


class XiaoHongShuApiClient:
    """
    XiaoHongShu API client with integrated browser session management.
    This client handles API communication through browser session for authentication.
    """

    def __init__(self, browser_session: AgentBrowserSession, timeout: int = 60, proxy: Optional[str] = None):
        """
        Initialize the RedBook API client
        
        Args:
            timeout: Request timeout in seconds¬
            proxy: Proxy URL if needed
        """
        self.browser_session = browser_session
        self.target_id = None
        self.proxy = proxy
        self.timeout = timeout
        self._api_base = "https://edith.xiaohongshu.com"
        self._web_base = "https://www.xiaohongshu.com"

        # Error constants
        self.NETWORK_ERROR_MSG = "Network connection error, please check network settings or restart"
        self.NETWORK_ERROR_CODE = 300012
        self.CONTENT_ERROR_MSG = "Content status abnormal, please check later"
        self.CONTENT_ERROR_CODE = -510001

        # Default headers
        self.default_headers = {
            'content-type': 'application/json;charset=UTF-8',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
        }
        self.cookies = {}

    async def _prepare_request_headers(self, endpoint, payload: Optional[Dict] = None):
        headers = copy.deepcopy(self.default_headers)

        js_expression = f"window._webmsxyw && window._webmsxyw('{endpoint}', {json.dumps(payload) if payload else 'null'})"
        cdp_session = await self.browser_session.get_or_create_cdp_session(target_id=self.target_id)
        result = await cdp_session.cdp_client.send.Runtime.evaluate(
            params={
                'expression': js_expression,
                'returnByValue': True,
                'awaitPromise': True
            },
            session_id=cdp_session.session_id,
        )

        encrypt_result = result.get('result', {}).get('value') if result else None
        if encrypt_result:
            # Get browser storage value
            b1_result = await cdp_session.cdp_client.send.Runtime.evaluate(
                params={
                    'expression': "window.localStorage.getItem('b1')",
                    'returnByValue': True,
                    'awaitPromise': True
                },
                session_id=cdp_session.session_id,
            )

            b1_storage = b1_result.get('result', {}).get('value') if b1_result else None
            # Create signature headers
            signature_headers = create_signature_headers(
                a1=self.cookies.get('a1', ''),
                b1=b1_storage or '',
                x_s=encrypt_result.get('X-s', ''),
                x_t=str(encrypt_result.get('X-t', ''))
            )
            headers.update(signature_headers)

        return headers

    async def get_me(self) -> Dict:
        """
        Get current user information to check login status

        Returns:
            User information dictionary
        """
        uri = '/api/sns/web/v2/user/me'
        return await self._make_request(
            "GET", f"{self._api_base}{uri}", headers=self.default_headers
        )

    async def setup(self, target_id: Optional[str] = None):
        """
        Get XiaoHongShu cookies and verify login status

        Args:
            browser_session: Main browser session to use for navigation

        Returns:
            Dict containing status and message

        Raises:
            AuthenticationError: If user is not logged in
        """
        try:
            if self.target_id and self.cookies:
                logger.info("Already setup. Return!")
                return

            if target_id:
                self.target_id = target_id
            else:
                self.target_id = await self.browser_session.navigate_to_url("https://www.xiaohongshu.com/",
                                                                            new_tab=True)
                await asyncio.sleep(2)

            cdp_session = await self.browser_session.get_or_create_cdp_session(target_id=target_id)
            result = await asyncio.wait_for(
                cdp_session.cdp_client.send.Storage.getCookies(session_id=cdp_session.session_id), timeout=8.0
            )
            web_cookies = result.get('cookies', [])

            cookie_str, cookie_dict = extract_cookies_from_browser(web_cookies)
            self.default_headers["Cookie"] = cookie_str
            self.cookies = cookie_dict

            if not self.cookies:
                raise AuthenticationError("No valid cookies found! Please Login first!")

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

            user_info = await self.get_me()
            if not user_info or 'user_id' not in user_info:
                self.cookies = {}
                del self.default_headers["Cookie"]
                raise AuthenticationError("No user login in xiaohongshu!")

        except Exception as e:
            logger.error(f"Failed to get XiaoHongShu cookies: {e}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    async def _make_request(self, method: str, url: str, **kwargs) -> Union[str, Dict]:
        """
        Make HTTP request with error handling

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional request parameters

        Returns:
            Response data
        """
        raw_response = kwargs.pop("raw_response", False)

        async with httpx.AsyncClient(proxy=self.proxy) as client:
            response = await client.request(method, url, timeout=self.timeout, **kwargs)

        # Handle verification challenges
        if response.status_code in [471, 461]:
            verify_type = response.headers.get("Verifytype", "")
            verify_uuid = response.headers.get("Verifyuuid", "")
            error_msg = f"Verification challenge detected, Verifytype: {verify_type}, Verifyuuid: {verify_uuid}"
            logger.error(error_msg)
            raise AuthenticationError(error_msg)

        if raw_response:
            return response.text

        try:
            data = response.json()
            if data.get("success"):
                return data.get("data", data.get("success", {}))
            elif data.get("code") == self.NETWORK_ERROR_CODE:
                raise NetworkError(self.NETWORK_ERROR_MSG)
            else:
                raise DataExtractionError(data.get("msg", "Request failed"))
        except json.JSONDecodeError:
            raise DataExtractionError(f"Invalid JSON response: {response.text}")

    async def _get_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """
        Make GET request with signature

        Args:
            endpoint: API endpoint
            params: URL parameters

        Returns:
            Response data
        """
        final_endpoint = endpoint
        if params:
            final_endpoint = f"{endpoint}?{urlencode(params)}"

        headers = await self._prepare_request_headers(final_endpoint)
        return await self._make_request(
            "GET", f"{self._api_base}{final_endpoint}", headers=headers
        )

    async def _post_request(self, endpoint: str, data: Dict, **kwargs) -> Dict:
        """
        Make POST request with signature

        Args:
            endpoint: API endpoint
            data: Request body data
            **kwargs: Additional parameters

        Returns:
            Response data
        """
        headers = await self._prepare_request_headers(endpoint, data)
        json_payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        return await self._make_request(
            "POST", f"{self._api_base}{endpoint}",
            data=json_payload, headers=headers, **kwargs
        )

    async def search_content_by_keyword(
            self,
            keyword: str,
            session_id: Optional[str] = None,
            page: int = 1,
            page_size: int = 20,
            sort_type: str = SearchType.GENERAL,
            content_type: int = ContentType.ALL,
    ) -> List:
        """
        Search content by keyword

        Args:
            keyword: Search keyword
            session_id: Search session ID (auto-generated if not provided)
            page: Page number
            page_size: Items per page
            sort_type: Sort method
            content_type: Content type filter

        Returns:
            Search results
        """
        if session_id is None:
            session_id = create_session_id()

        endpoint = "/api/sns/web/v1/search/notes"
        payload = {
            "keyword": keyword,
            "page": page,
            "page_size": page_size,
            "search_id": session_id,
            "sort": sort_type,
            "note_type": content_type,
        }
        result = await self._post_request(endpoint, payload)
        return result.get('items', [])

    async def fetch_content_details(
            self,
            content_id: str,
            xsec_token: str,
            source_channel: str = "pc_search",
    ) -> Dict:
        """
        Fetch detailed content information

        Args:
            content_id: Content ID
            source_channel: Source channel identifier
            security_token: Security token

        Returns:
            Content details
        """
        payload = {
            "source_note_id": content_id,
            "image_formats": ["jpg", "webp", "avif"],
            "extra": {"need_body_topic": 1},
            "xsec_source": source_channel,
            "xsec_token": xsec_token,
        }
        endpoint = "/api/sns/web/v1/feed"
        result = await self._post_request(endpoint, payload)

        if result and result.get("items"):
            return result["items"][0]["note_card"]

        logger.error(f"Failed to fetch content {content_id}, response: {result}")
        return {}

    async def fetch_content_comments(
            self,
            content_id: str,
            xsec_token: str,
            cursor: str = "",
    ) -> Dict:
        """
        Fetch content comments (first level)

        Args:
            content_id: Content ID
            security_token: Security token
            cursor: Pagination cursor

        Returns:
            Comments data
        """
        endpoint = "/api/sns/web/v2/comment/page"
        params = {
            "note_id": content_id,
            "cursor": cursor,
            "top_comment_id": "",
            "image_formats": "jpg,webp,avif",
            "xsec_token": xsec_token,
        }
        return await self._get_request(endpoint, params)

    async def fetch_all_content_comments(
            self,
            content_id: str,
            xsec_token: str,
            fetch_interval: float = 1.0,
            progress_callback: Optional[Callable] = None,
            max_comments: int = 1000,
    ) -> List[Dict]:
        """
        Fetch all comments for content (including pagination)

        Args:
            content_id: Content ID
            security_token: Security token
            fetch_interval: Interval between requests in seconds
            progress_callback: Callback function for progress updates
            max_comments: Maximum comments to fetch

        Returns:
            List of all comments
        """
        all_comments = []
        has_more = True
        cursor = ""

        while has_more and len(all_comments) < max_comments:
            comments_data = await self.fetch_content_comments(
                content_id, xsec_token, cursor
            )
            has_more = comments_data.get("has_more", False)
            cursor = comments_data.get("cursor", "")

            if "comments" not in comments_data:
                logger.info(f"No more comments found: {comments_data}")
                break

            batch_comments = comments_data["comments"]
            remaining_slots = max_comments - len(all_comments)

            if remaining_slots <= 0:
                break

            if len(batch_comments) > remaining_slots:
                batch_comments = batch_comments[:remaining_slots]

            if progress_callback:
                await progress_callback(content_id, batch_comments)

            await asyncio.sleep(fetch_interval)
            all_comments.extend(batch_comments)

        logger.info(f"Fetched {len(all_comments)} comments for content {content_id}")
        return all_comments

    async def get_user_profile(self, user_id: str) -> Dict:
        """
        Get user profile information

        Args:
            user_id: User ID

        Returns:
            User profile data
        """
        endpoint = f"/user/profile/{user_id}"
        try:
            html_response = await self._make_request(
                "GET", self._web_base + endpoint,
                raw_response=True, headers=self.default_headers
            )

            # Extract user info from HTML response
            if "window.__INITIAL_STATE__" in html_response:
                profile_data = {
                    "user_id": user_id,
                    "status": "active",
                    "response_length": len(html_response)
                }
                return profile_data
            else:
                return {"user_id": user_id, "error": "Failed to extract profile data"}

        except Exception as e:
            logger.error(f"Failed to get user profile for {user_id}: {e}")
            return {"user_id": user_id, "error": str(e)}

    async def fetch_user_content(
            self,
            user_id: str,
            cursor: str = "",
            page_size: int = 30,
    ) -> Dict:
        """
        Fetch content by user

        Args:
            user_id: User ID
            cursor: Last content ID for pagination
            page_size: Number of items per page

        Returns:
            User content data
        """
        endpoint = "/api/sns/web/v1/user_posted"
        params = {
            "user_id": user_id,
            "cursor": cursor,
            "num": page_size,
            "image_formats": "jpg,webp,avif",
        }
        return await self._get_request(endpoint, params)

    async def fetch_all_user_content(
            self,
            user_id: str,
            fetch_interval: float = 1.0,
            progress_callback: Optional[Callable] = None,
            max_content: int = 1000,
    ) -> List[Dict]:
        """
        Fetch all content by user

        Args:
            user_id: User ID
            fetch_interval: Interval between requests in seconds
            progress_callback: Callback function for progress updates
            max_content: Maximum content items to fetch

        Returns:
            List of all user content
        """
        all_content = []
        has_more = True
        cursor = ""

        while has_more and len(all_content) < max_content:
            content_data = await self.fetch_user_content(user_id, cursor)
            if not content_data:
                logger.error(f"User {user_id} may be restricted or data unavailable")
                break

            has_more = content_data.get("has_more", False)
            cursor = content_data.get("cursor", "")

            if "notes" not in content_data:
                logger.info(f"No content found: {content_data}")
                break

            batch_content = content_data["notes"]
            logger.info(f"Fetched {len(batch_content)} content items for user {user_id}")

            remaining_slots = max_content - len(all_content)
            if remaining_slots <= 0:
                break

            content_to_add = batch_content[:remaining_slots]
            if progress_callback:
                await progress_callback(content_to_add)

            all_content.extend(content_to_add)
            await asyncio.sleep(fetch_interval)

        logger.info(f"Fetched {len(all_content)} content items for user {user_id}")
        return all_content

    async def get_home_recommendations(self) -> List:
        """
        Get home feed recommendations with proper header signature

        Returns:
            Home feed data
        """
        payload = {
            "category": "homefeed_recommend",
            "cursor_score": "",
            "image_formats": json.dumps(["jpg", "webp", "avif"], separators=(",", ":")),
            "need_filter_image": False,
            "need_num": 8,
            "num": 18,
            "note_index": 33,
            "refresh_type": 1,
            "search_key": "",
            "unread_begin_note_id": "",
            "unread_end_note_id": "",
            "unread_note_count": 0
        }
        endpoint = "/api/sns/web/v1/homefeed"

        # Prepare headers with signature specifically for home feed
        headers = await self._prepare_request_headers(endpoint, payload)

        # Make the request with proper headers
        json_payload = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        result = await self._make_request(
            "POST", f"{self._api_base}{endpoint}",
            data=json_payload, headers=headers
        )
        return result.get("items", [])

    async def submit_comment(self, content_id: str, comment_text: str) -> Dict:
        """
        Submit comment to content

        Args:
            content_id: Content ID
            comment_text: Comment text

        Returns:
            Submit result
        """
        endpoint = '/api/sns/web/v1/comment/post'
        payload = {
            "note_id": content_id,
            "content": comment_text,
            "at_users": []
        }
        return await self._post_request(endpoint, payload)
