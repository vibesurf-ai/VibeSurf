import asyncio
import json
import time
from typing import Dict, List, Optional, Callable, Union, Any
import httpx
from urllib.parse import urlencode
import random
from tenacity import retry, stop_after_attempt, wait_fixed

from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.logger import get_logger
from .utils import (
    get_search_id, convert_cookies, extract_note_id_token, 
    generate_trace_id, IPBlockError, DataFetchError,
    SearchSortType, SearchNoteType
)

logger = get_logger(__name__)


class XiaoHongShuClient:

    def __init__(self, timeout=60, proxy=None):
        self.proxy = proxy
        self.timeout = timeout
        self._host = "https://edith.xiaohongshu.com"
        self._domain = "https://www.xiaohongshu.com"
        self.IP_ERROR_STR = "Network connection error, please check network settings or restart"
        self.IP_ERROR_CODE = 300012
        self.NOTE_ABNORMAL_STR = "Note status abnormal, please check later"
        self.NOTE_ABNORMAL_CODE = -510001
        self.headers = {
            'content-type': 'application/json;charset=UTF-8',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
        }
        self.cookie_dict = {}

    async def _get_xhs_cookies(self, browser_session: AgentBrowserSession) -> Dict[str, str]:
        """Get XiaoHongShu related cookies from browser session"""
        try:
            web_cookies = await browser_session._cdp_get_cookies()
            cookie_str, cookie_dict = convert_cookies(web_cookies)
            self.headers["Cookie"] = cookie_str
            self.cookie_dict = cookie_dict
            return cookie_dict
        except Exception as e:
            logger.error(f"Failed to get cookies from browser session: {e}")
            return {}

    async def _pre_headers(self, browser_session: AgentBrowserSession, url: str, data=None) -> Dict:
        """
        Request header parameter signing using browser session
        Args:
            browser_session: Browser session for JS execution
            url: Request URL
            data: Request data

        Returns:
            Updated headers dict
        """
        try:
            # Execute JS function in browser to get encryption parameters
            encrypt_params = await browser_session.evaluate_js(
                f"window._webmsxyw && window._webmsxyw('{url}', {json.dumps(data) if data else 'null'})"
            )
            
            if encrypt_params:
                # Get local storage b1 value
                b1_value = await browser_session.evaluate_js("window.localStorage.getItem('b1')")
                
                # Simple header generation (without complex signing for now)
                headers = {
                    "X-S": encrypt_params.get("X-s", ""),
                    "X-T": str(encrypt_params.get("X-t", "")),
                    "X-B3-Traceid": generate_trace_id(),
                }
                self.headers.update(headers)
                
        except Exception as e:
            logger.warning(f"Failed to generate signature headers: {e}")
            # Continue without signature headers
            
        return self.headers

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    async def request(self, browser_session: AgentBrowserSession, method: str, url: str, **kwargs) -> Union[str, Any]:
        """
        Encapsulated httpx common request method with response processing
        Args:
            browser_session: Browser session for cookie management
            method: Request method
            url: Request URL
            **kwargs: Other request parameters

        Returns:
            Response data
        """
        return_response = kwargs.pop("return_response", False)
        
        # Ensure we have valid cookies
        await self._get_xhs_cookies(browser_session)
        if not self.cookie_dict:
            await browser_session.navigate_to_url("https://www.xiaohongshu.com", new_tab=False)
            raise Exception("No XHS cookies found. Please login to xiaohongshu.com first.")

        async with httpx.AsyncClient(proxy=self.proxy) as client:
            response = await client.request(method, url, timeout=self.timeout, **kwargs)

        if response.status_code == 471 or response.status_code == 461:
            verify_type = response.headers.get("Verifytype", "")
            verify_uuid = response.headers.get("Verifyuuid", "")
            msg = f"Captcha appeared, request failed, Verifytype: {verify_type}, Verifyuuid: {verify_uuid}"
            logger.error(msg)
            raise Exception(msg)

        if return_response:
            return response.text
            
        try:
            data: Dict = response.json()
            if data.get("success"):
                return data.get("data", data.get("success", {}))
            elif data.get("code") == self.IP_ERROR_CODE:
                raise IPBlockError(self.IP_ERROR_STR)
            else:
                raise DataFetchError(data.get("msg", "Request failed"))
        except json.JSONDecodeError:
            raise DataFetchError(f"Invalid JSON response: {response.text}")

    async def get(self, browser_session: AgentBrowserSession, uri: str, params=None) -> Dict:
        """
        GET request with header signing
        Args:
            browser_session: Browser session
            uri: Request URI
            params: Request parameters

        Returns:
            Response data
        """
        final_uri = uri
        if isinstance(params, dict):
            final_uri = f"{uri}?{urlencode(params)}"
        
        headers = await self._pre_headers(browser_session, final_uri)
        return await self.request(
            browser_session, "GET", f"{self._host}{final_uri}", headers=headers
        )

    async def post(self, browser_session: AgentBrowserSession, uri: str, data: dict, **kwargs) -> Dict:
        """
        POST request with header signing
        Args:
            browser_session: Browser session
            uri: Request URI
            data: Request body parameters

        Returns:
            Response data
        """
        headers = await self._pre_headers(browser_session, uri, data)
        json_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        return await self.request(
            browser_session, "POST", f"{self._host}{uri}", 
            data=json_str, headers=headers, **kwargs
        )

    async def get_note_media(self, url: str) -> Union[bytes, None]:
        """Download note media content"""
        async with httpx.AsyncClient(proxy=self.proxy) as client:
            try:
                response = await client.request("GET", url, timeout=self.timeout)
                response.raise_for_status()
                return response.content
            except httpx.HTTPError as exc:
                logger.error(f"Failed to download media from {url}: {exc}")
                return None

    async def pong(self, browser_session: AgentBrowserSession) -> bool:
        """
        Check if login state is valid
        Returns:
            True if login is valid, False otherwise
        """
        logger.info("Checking XHS login state...")
        try:
            note_card = await self.get_note_by_keyword(browser_session, keyword="小红书")
            return bool(note_card.get("items"))
        except Exception as e:
            logger.error(f"Ping XHS failed: {e}")
            return False

    async def update_cookies(self, browser_session: AgentBrowserSession):
        """
        Update cookies from browser session
        Args:
            browser_session: Browser session object
        """
        await self._get_xhs_cookies(browser_session)

    async def get_note_by_keyword(
        self,
        browser_session: AgentBrowserSession,
        keyword: str,
        search_id: str = None,
        page: int = 1,
        page_size: int = 20,
        sort: str = SearchSortType.GENERAL,
        note_type: int = SearchNoteType.ALL,
    ) -> Dict:
        """
        Search notes by keyword
        Args:
            browser_session: Browser session
            keyword: Search keyword
            search_id: Search ID (auto-generated if not provided)
            page: Page number
            page_size: Page size
            sort: Sort type
            note_type: Note type

        Returns:
            Search results
        """
        if search_id is None:
            search_id = get_search_id()
            
        uri = "/api/sns/web/v1/search/notes"
        data = {
            "keyword": keyword,
            "page": page,
            "page_size": page_size,
            "search_id": search_id,
            "sort": sort,
            "note_type": note_type,
        }
        return await self.post(browser_session, uri, data)

    async def get_note_by_id(
        self,
        browser_session: AgentBrowserSession,
        note_id: str,
        xsec_source: str = "pc_search",
        xsec_token: str = "",
    ) -> Dict:
        """
        Get note details by ID
        Args:
            browser_session: Browser session
            note_id: Note ID
            xsec_source: Source channel
            xsec_token: Security token

        Returns:
            Note details
        """
        data = {
            "source_note_id": note_id,
            "image_formats": ["jpg", "webp", "avif"],
            "extra": {"need_body_topic": 1},
            "xsec_source": xsec_source,
            "xsec_token": xsec_token,
        }
        uri = "/api/sns/web/v1/feed"
        res = await self.post(browser_session, uri, data)
        if res and res.get("items"):
            return res["items"][0]["note_card"]
        
        logger.error(f"Failed to get note {note_id}, response: {res}")
        return {}

    async def get_note_comments(
        self,
        browser_session: AgentBrowserSession,
        note_id: str,
        xsec_token: str,
        cursor: str = "",
    ) -> Dict:
        """
        Get first-level comments of a note
        Args:
            browser_session: Browser session
            note_id: Note ID
            xsec_token: Security token
            cursor: Pagination cursor

        Returns:
            Comments data
        """
        uri = "/api/sns/web/v2/comment/page"
        params = {
            "note_id": note_id,
            "cursor": cursor,
            "top_comment_id": "",
            "image_formats": "jpg,webp,avif",
            "xsec_token": xsec_token,
        }
        return await self.get(browser_session, uri, params)

    async def get_note_all_comments(
        self,
        browser_session: AgentBrowserSession,
        note_id: str,
        xsec_token: str,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
        max_count: int = 1000,
    ) -> List[Dict]:
        """
        Get all comments of a note (including sub-comments)
        Args:
            browser_session: Browser session
            note_id: Note ID
            xsec_token: Security token
            crawl_interval: Crawl interval in seconds
            callback: Callback function after each batch
            max_count: Maximum number of comments to fetch

        Returns:
            List of all comments
        """
        result = []
        comments_has_more = True
        comments_cursor = ""
        
        while comments_has_more and len(result) < max_count:
            comments_res = await self.get_note_comments(
                browser_session, note_id, xsec_token, comments_cursor
            )
            comments_has_more = comments_res.get("has_more", False)
            comments_cursor = comments_res.get("cursor", "")
            
            if "comments" not in comments_res:
                logger.info(f"No comments found in response: {comments_res}")
                break
                
            comments = comments_res["comments"]
            if len(result) + len(comments) > max_count:
                comments = comments[: max_count - len(result)]
                
            if callback:
                await callback(note_id, comments)
                
            await asyncio.sleep(crawl_interval)
            result.extend(comments)
            
        logger.info(f"Retrieved {len(result)} comments for note {note_id}")
        return result

    async def get_creator_info(self, browser_session: AgentBrowserSession, user_id: str) -> Dict:
        """
        Get creator information by parsing user profile page
        Args:
            browser_session: Browser session
            user_id: User ID

        Returns:
            Creator information
        """
        uri = f"/user/profile/{user_id}"
        try:
            html_content = await self.request(
                browser_session, "GET", self._domain + uri, 
                return_response=True, headers=self.headers
            )
            
            # Extract creator info from HTML (simplified version)
            # In a real implementation, you would parse the HTML to extract window.__INITIAL_STATE__
            if "window.__INITIAL_STATE__" in html_content:
                # This is a simplified extraction - in practice you'd need proper HTML parsing
                creator_info = {
                    "user_id": user_id,
                    "status": "active",
                    "html_length": len(html_content)
                }
                return creator_info
            else:
                return {"user_id": user_id, "error": "Failed to extract creator info"}
                
        except Exception as e:
            logger.error(f"Failed to get creator info for {user_id}: {e}")
            return {"user_id": user_id, "error": str(e)}

    async def get_notes_by_creator(
        self,
        browser_session: AgentBrowserSession,
        creator: str,
        cursor: str = "",
        page_size: int = 30,
    ) -> Dict:
        """
        Get notes by creator
        Args:
            browser_session: Browser session
            creator: Creator ID
            cursor: Last note ID from previous page
            page_size: Page size

        Returns:
            Notes data
        """
        uri = "/api/sns/web/v1/user_posted"
        params = {
            "user_id": creator,
            "cursor": cursor,
            "num": page_size,
            "image_formats": "jpg,webp,avif",
        }
        return await self.get(browser_session, uri, params)

    async def get_all_notes_by_creator(
        self,
        browser_session: AgentBrowserSession,
        user_id: str,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
        max_count: int = 1000,
    ) -> List[Dict]:
        """
        Get all notes by a creator
        Args:
            browser_session: Browser session
            user_id: Creator user ID
            crawl_interval: Crawl interval in seconds
            callback: Callback function after each batch
            max_count: Maximum number of notes to fetch

        Returns:
            List of all notes by the creator
        """
        result = []
        notes_has_more = True
        notes_cursor = ""
        
        while notes_has_more and len(result) < max_count:
            notes_res = await self.get_notes_by_creator(browser_session, user_id, notes_cursor)
            if not notes_res:
                logger.error(f"Creator {user_id} may be banned or data unavailable")
                break

            notes_has_more = notes_res.get("has_more", False)
            notes_cursor = notes_res.get("cursor", "")
            
            if "notes" not in notes_res:
                logger.info(f"No notes found in response: {notes_res}")
                break

            notes = notes_res["notes"]
            logger.info(f"Got {len(notes)} notes for user {user_id}")

            remaining = max_count - len(result)
            if remaining <= 0:
                break

            notes_to_add = notes[:remaining]
            if callback:
                await callback(notes_to_add)

            result.extend(notes_to_add)
            await asyncio.sleep(crawl_interval)

        logger.info(f"Retrieved {len(result)} notes for creator {user_id}")
        return result

    async def home_feed(self, browser_session: AgentBrowserSession) -> Dict:
        """
        Get home feed recommendations
        Args:
            browser_session: Browser session

        Returns:
            Home feed data
        """
        data = {
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
        uri = "/api/sns/web/v1/homefeed"
        return await self.post(browser_session, uri, data)

    async def post_comment(self, browser_session: AgentBrowserSession, note_id: str, comment: str) -> Dict:
        """
        Post comment to note
        Args:
            browser_session: Browser session
            note_id: Note ID
            comment: Comment content

        Returns:
            Post result
        """
        uri = '/api/sns/web/v1/comment/post'
        data = {
            "note_id": note_id,
            "content": comment,
            "at_users": []
        }
        return await self.post(browser_session, uri, data)