import asyncio
import json
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import urlencode
import httpx
from tenacity import retry, stop_after_attempt, wait_fixed

from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.logger import get_logger
from vibe_surf.tools.website_api.base_client import BaseAPIClient

from .helpers import (
    SearchTime, SearchType, SearchSort,
    extract_cookies_from_browser, sign,
    ZhihuError, DataExtractionError, AuthenticationError, VerificationError,
    ZhihuExtractor, ZHIHU_URL, ZHIHU_ZHUANLAN_URL
)

logger = get_logger(__name__)


class ZhiHuClient(BaseAPIClient):
    """
    Zhihu API client with integrated browser session management.
    """

    def __init__(self, browser_session: AgentBrowserSession, timeout: int = 10, proxy: Optional[str] = None):
        super().__init__(browser_session, timeout, proxy)
        """
        Initialize the Zhihu API client
        
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
        
        # Default headers
        self.default_headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
            "accept": "*/*",
            "accept-language": "zh-CN,zh;q=0.9",
            "priority": "u=1, i",
            "x-api-version": "3.0.91",
            "x-app-za": "OS=Web",
            "x-requested-with": "fetch",
            "x-zse-93": "101_3_3.0",
        }
        self.cookie_dict = {}
        self._extractor = ZhihuExtractor()

    async def setup(self, target_id: Optional[str] = None):
        """
        Setup Zhihu client by navigating to the site and extracting cookies
        
        Args:
            target_id: Specific target ID to use, or None to create new
            
        Raises:
            AuthenticationError: If unable to access Zhihu properly
        """
        try:
            if self.target_id and self.cookie_dict:
                logger.info("Zhihu client already setup. Returning!")
                return

            if target_id:
                self.target_id = target_id
            else:
                self.target_id = await self.browser_session.navigate_to_url(
                    "https://www.zhihu.com/", new_tab=True
                )
                await asyncio.sleep(2)
                self.new_tab = True

            # Navigate to search page to get proper cookies
            logger.info("[ZhiHuClient.setup] Zhihu navigating to search page to get cookies, this takes about 5 seconds")
            await self.browser_session.navigate_to_url(
                f"{ZHIHU_URL}/search?q=python&search_source=Guess&utm_content=search_hot&type=content",
                new_tab=True,
            )
            await asyncio.sleep(5)

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
                self.default_headers["cookie"] = cookie_str
            self.cookie_dict = cookie_dict

            is_logged_in = await self.pong()
            if not is_logged_in:
                self.cookie_dict = {}
                if "cookie" in self.default_headers:
                    del self.default_headers["cookie"]
                raise AuthenticationError(f"Please login in [知乎]({ZHIHU_URL}) first!")

            logger.info(f"Zhihu client setup completed with {len(cookie_dict)} cookies")

        except Exception as e:
            logger.error(f"Failed to setup Zhihu client: {e}")
            raise AuthenticationError(f"Zhihu client setup failed: {e}")

    async def _pre_headers(self, url: str) -> Dict:
        """
        Request header parameter signing
        Args:
            url: Request URL with query parameters
        Returns:
            Headers dictionary with signatures
        """
        d_c0 = self.cookie_dict.get("d_c0")
        if not d_c0:
            raise Exception("d_c0 not found in cookies")
        
        sign_res = sign(url, self.default_headers["cookie"])
        headers = self.default_headers.copy()
        headers['x-zst-81'] = sign_res.get("x-zst-81", "")
        headers['x-zse-96'] = sign_res.get("x-zse-96", "")
        return headers

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    async def request(self, method: str, url: str, **kwargs) -> Union[str, Any]:
        """
        HTTP request wrapper with error handling
        
        Args:
            method: Request method
            url: Request URL
            **kwargs: Other request parameters
            
        Returns:
            Response data
        """
        return_response = kwargs.pop('return_response', False)

        async with httpx.AsyncClient(proxy=self.proxy) as client:
            response = await client.request(method, url, timeout=self.timeout, **kwargs)

        if response.status_code != 200:
            logger.error(f"[ZhiHuClient.request] Request Url: {url}, Request error: {response.text}")
            if response.status_code == 403:
                raise VerificationError(response.text)
            elif response.status_code == 404:
                return {}

            raise DataExtractionError(response.text)

        if return_response:
            return response.text
            
        try:
            data: Dict = response.json()
            if data.get("error"):
                logger.error(f"[ZhiHuClient.request] Request error: {data}")
                raise DataExtractionError(data.get("error", {}).get("message"))
            return data
        except json.JSONDecodeError:
            logger.error(f"[ZhiHuClient.request] Request error: {response.text}")
            raise DataExtractionError(response.text)

    async def get(self, uri: str, params=None, **kwargs) -> Union[Dict, str]:
        """
        GET request with header signing
        
        Args:
            uri: Request URI
            params: Request parameters
            
        Returns:
            Response data
        """
        final_uri = uri
        if isinstance(params, dict):
            final_uri += '?' + urlencode(params)
        
        headers = await self._pre_headers(final_uri)
        base_url = (ZHIHU_URL if "/p/" not in uri else ZHIHU_ZHUANLAN_URL)
        return await self.request(method="GET", url=base_url + final_uri, headers=headers, **kwargs)

    async def pong(self) -> bool:
        """
        Check if login status is valid
        
        Returns:
            True if logged in, False otherwise
        """
        logger.info("[ZhiHuClient.pong] Begin to pong zhihu...")
        ping_flag = False
        try:
            res = await self.get_current_user_info()
            if res.get("uid") and res.get("name"):
                ping_flag = True
                logger.info("[ZhiHuClient.pong] Ping zhihu successfully")
            else:
                logger.error(f"[ZhiHuClient.pong] Ping zhihu failed, response data: {res}")
        except Exception as e:
            logger.error(f"[ZhiHuClient.pong] Ping zhihu failed: {e}, and try to login again...")
            ping_flag = False
        return ping_flag

    async def update_cookies(self):
        """Update cookies from browser context"""
        try:
            cdp_session = await self.browser_session.get_or_create_cdp_session(target_id=self.target_id)
            result = await asyncio.wait_for(
                cdp_session.cdp_client.send.Storage.getCookies(session_id=cdp_session.session_id),
                timeout=8.0
            )
            web_cookies = result.get('cookies', [])
            cookie_str, cookie_dict = extract_cookies_from_browser(web_cookies)
            if cookie_str:
                self.default_headers["cookie"] = cookie_str
            self.cookie_dict = cookie_dict
        except Exception as e:
            logger.error(f"Failed to update cookies: {e}")

    async def get_current_user_info(self) -> Dict:
        """Get current logged in user information"""
        params = {"include": "email,is_active,is_bind_phone"}
        return await self.get("/api/v4/me", params)

    async def get_note_by_keyword(
        self,
        keyword: str,
        page: int = 1,
        page_size: int = 20,
        sort: str = 'upvoted_count',
        note_type: str = '',
        search_time: str = '',
    ) -> List[Dict]:
        """
        Search content by keyword
        
        Args:
            keyword: Search keyword
            page: Page number
            page_size: Items per page
            sort: Sort method
            note_type: Content type filter
            search_time: Time range filter
            
        Returns:
            List of content dictionaries
        """
        uri = "/api/v4/search_v3"
        params = {
            "gk_version": "gz-gaokao",
            "t": "general",
            "q": keyword,
            "correction": 1,
            "offset": (page - 1) * page_size,
            "limit": page_size,
            "filter_fields": "",
            "lc_idx": (page - 1) * page_size,
            "show_all_topics": 0,
            "search_source": "Filter",
            "time_interval": search_time,
            "sort": sort,
            "vertical": note_type,
        }
        search_res = await self.get(uri, params)
        logger.debug(f"[ZhiHuClient.get_note_by_keyword] Search result: {search_res}")
        return self._extractor.extract_contents_from_search(search_res)

    async def get_root_comments(
        self,
        content_id: str,
        content_type: str,
        offset: str = "",
        limit: int = 10,
        order_by: str = "score",
    ) -> Dict:
        """
        Get root level comments for content
        
        Args:
            content_id: Content ID
            content_type: Content type (answer, article, zvideo)
            offset: Pagination offset
            limit: Items per page
            order_by: Sort order
            
        Returns:
            Comments response data
        """
        uri = f"/api/v4/comment_v5/{content_type}s/{content_id}/root_comment"
        params = {"order": order_by, "offset": offset, "limit": limit}
        return await self.get(uri, params)

    async def get_child_comments(
        self,
        root_comment_id: str,
        offset: str = "",
        limit: int = 10,
        order_by: str = "sort",
    ) -> Dict:
        """
        Get child comments under a root comment
        
        Args:
            root_comment_id: Parent comment ID
            offset: Pagination offset
            limit: Items per page
            order_by: Sort order
            
        Returns:
            Child comments response data
        """
        uri = f"/api/v4/comment_v5/comment/{root_comment_id}/child_comment"
        params = {
            "order": order_by,
            "offset": offset,
            "limit": limit,
        }
        return await self.get(uri, params)

    async def get_all_comments(
        self,
        content_id: str,
        content_type: str,
        crawl_interval: float = 1.0,
        limit: int = 10,
        max_comments: int = 100,
        include_sub_comments: bool = False,
        callback: Optional[Callable] = None,
    ) -> List[Dict]:
        """
        Get all comments (root and child) for a content item
        
        Args:
            content_id: Content ID
            content_type: Content type (answer, article, zvideo)
            crawl_interval: Delay between requests
            callback: Callback function after fetching each batch
            
        Returns:
            List of all comment dictionaries
        """
        result: List[Dict] = []
        is_end: bool = False
        offset: str = ""
        
        # Create content dict for extractor
        content = {"content_id": content_id, "content_type": content_type}
        
        while not is_end:
            root_comment_res = await self.get_root_comments(content_id, content_type, offset, limit)
            if not root_comment_res:
                break
                
            paging_info = root_comment_res.get("paging", {})
            is_end = paging_info.get("is_end", True)
            offset = self._extractor.extract_offset(paging_info)
            comments = self._extractor.extract_comments(content, root_comment_res.get("data", []))

            if not comments:
                break

            if callback:
                await callback(comments)

            result.extend(comments)
            if include_sub_comments:
                sub_comments = await self._get_comments_all_sub_comments(content_id, content_type, comments, crawl_interval=crawl_interval, callback=callback)
                result.extend(sub_comments)
            if len(result) >= max_comments:
                break
            await asyncio.sleep(crawl_interval)
            
        return result

    async def _get_comments_all_sub_comments(
        self,
        content_id: str,
        content_type: str,
        comments: List[Dict],
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
    ) -> List[Dict]:
        """
        Get all sub-comments for given comments
        
        Args:
            content_id: Content ID
            content_type: Content type (answer, article, zvideo)
            comments: List of parent comment dictionaries
            crawl_interval: Delay between requests
            callback: Callback function after fetching each batch
            
        Returns:
            List of all sub-comment dictionaries
        """
        all_sub_comments: List[Dict] = []
        
        # Create content dict for extractor
        content = {"content_id": content_id, "content_type": content_type}
        
        for parent_comment in comments:
            if parent_comment.get("sub_comment_count", 0) == 0:
                continue

            is_end: bool = False
            offset: str = ""
            limit: int = 10
            
            while not is_end:
                child_comment_res = await self.get_child_comments(parent_comment["comment_id"], offset, limit)
                if not child_comment_res:
                    break
                    
                paging_info = child_comment_res.get("paging", {})
                is_end = paging_info.get("is_end", True)
                offset = self._extractor.extract_offset(paging_info)
                sub_comments = self._extractor.extract_comments(content, child_comment_res.get("data", []))

                if not sub_comments:
                    break

                if callback:
                    await callback(sub_comments)

                all_sub_comments.extend(sub_comments)
                await asyncio.sleep(crawl_interval)
                
        return all_sub_comments

    async def get_creator_info(self, url_token: str) -> Optional[Dict]:
        """
        Get creator information
        
        Args:
            url_token: Creator's url token
            
        Returns:
            ZhihuCreator object or None
        """
        uri = f"/people/{url_token}"
        html_content: str = await self.get(uri, return_response=True)
        return self._extractor.extract_creator(url_token, html_content)

    async def get_creator_answers(self, url_token: str, offset: int = 0, limit: int = 20) -> Dict:
        """
        Get creator's answers
        
        Args:
            url_token: Creator's url token
            offset: Pagination offset
            limit: Items per page
            
        Returns:
            Response data
        """
        uri = f"/api/v4/members/{url_token}/answers"
        params = {
            "include":
            "data[*].is_normal,admin_closed_comment,reward_info,is_collapsed,annotation_action,annotation_detail,collapse_reason,collapsed_by,suggest_edit,comment_count,can_comment,content,editable_content,attachment,voteup_count,reshipment_settings,comment_permission,created_time,updated_time,review_info,excerpt,paid_info,reaction_instruction,is_labeled,label_info,relationship.is_authorized,voting,is_author,is_thanked,is_nothelp;data[*].vessay_info;data[*].author.badge[?(type=best_answerer)].topics;data[*].author.vip_info;data[*].question.has_publishing_draft,relationship",
            "offset": offset,
            "limit": limit,
            "order_by": "created"
        }
        return await self.get(uri, params)

    async def get_creator_articles(self, url_token: str, offset: int = 0, limit: int = 20) -> Dict:
        """
        Get creator's articles
        
        Args:
            url_token: Creator's url token
            offset: Pagination offset
            limit: Items per page
            
        Returns:
            Response data
        """
        uri = f"/api/v4/members/{url_token}/articles"
        params = {
            "include":
            "data[*].comment_count,suggest_edit,is_normal,thumbnail_extra_info,thumbnail,can_comment,comment_permission,admin_closed_comment,content,voteup_count,created,updated,upvoted_followees,voting,review_info,reaction_instruction,is_labeled,label_info;data[*].vessay_info;data[*].author.badge[?(type=best_answerer)].topics;data[*].author.vip_info;",
            "offset": offset,
            "limit": limit,
            "order_by": "created"
        }
        return await self.get(uri, params)

    async def get_creator_videos(self, url_token: str, offset: int = 0, limit: int = 20) -> Dict:
        """
        Get creator's videos
        
        Args:
            url_token: Creator's url token
            offset: Pagination offset
            limit: Items per page
            
        Returns:
            Response data
        """
        uri = f"/api/v4/members/{url_token}/zvideos"
        params = {
            "include": "similar_zvideo,creation_relationship,reaction_instruction",
            "offset": offset,
            "limit": limit,
            "similar_aggregation": "true",
        }
        return await self.get(uri, params)

    async def get_all_answer_by_creator(
        self,
        url_token: str,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None
    ) -> List[Dict]:
        """
        Get all answers by creator
        
        Args:
            url_token: Creator's url token
            crawl_interval: Delay between requests
            callback: Callback function after fetching each batch
            
        Returns:
            List of all content dictionaries
        """
        all_contents: List[Dict] = []
        is_end: bool = False
        offset: int = 0
        limit: int = 20
        
        while not is_end:
            res = await self.get_creator_answers(url_token, offset, limit)
            if not res:
                break
                
            logger.info(f"[ZhiHuClient.get_all_anwser_by_creator] Get creator {url_token} answers: {res}")
            paging_info = res.get("paging", {})
            is_end = paging_info.get("is_end", True)
            contents = self._extractor.extract_content_list_from_creator(res.get("data", []))
            
            if callback:
                await callback(contents)
                
            all_contents.extend(contents)
            offset += limit
            await asyncio.sleep(crawl_interval)
            
        return all_contents

    async def get_all_articles_by_creator(
        self,
        url_token: str,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
    ) -> List[Dict]:
        """
        Get all articles by creator
        
        Args:
            url_token: Creator's url token
            crawl_interval: Delay between requests
            callback: Callback function after fetching each batch
            
        Returns:
            List of all content dictionaries
        """
        all_contents: List[Dict] = []
        is_end: bool = False
        offset: int = 0
        limit: int = 20
        
        while not is_end:
            res = await self.get_creator_articles(url_token, offset, limit)
            if not res:
                break
                
            paging_info = res.get("paging", {})
            is_end = paging_info.get("is_end", True)
            contents = self._extractor.extract_content_list_from_creator(res.get("data", []))
            
            if callback:
                await callback(contents)
                
            all_contents.extend(contents)
            offset += limit
            await asyncio.sleep(crawl_interval)
            
        return all_contents

    async def get_all_videos_by_creator(
        self,
        url_token: str,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
    ) -> List[Dict]:
        """
        Get all videos by creator
        
        Args:
            url_token: Creator's url token
            crawl_interval: Delay between requests
            callback: Callback function after fetching each batch
            
        Returns:
            List of all content dictionaries
        """
        all_contents: List[Dict] = []
        is_end: bool = False
        offset: int = 0
        limit: int = 20
        
        while not is_end:
            res = await self.get_creator_videos(url_token, offset, limit)
            if not res:
                break
                
            paging_info = res.get("paging", {})
            is_end = paging_info.get("is_end", True)
            contents = self._extractor.extract_content_list_from_creator(res.get("data", []))
            
            if callback:
                await callback(contents)
                
            all_contents.extend(contents)
            offset += limit
            await asyncio.sleep(crawl_interval)
            
        return all_contents

    async def get_answer_info(
        self,
        question_id: str,
        answer_id: str,
    ) -> Optional[Dict]:
        """
        Get answer information
        
        Args:
            question_id: Question ID
            answer_id: Answer ID
            
        Returns:
            Content dictionary or None
        """
        uri = f"/question/{question_id}/answer/{answer_id}"
        response_html = await self.get(uri, return_response=True)
        return self._extractor.extract_answer_content_from_html(response_html)

    async def get_article_info(self, article_id: str) -> Optional[Dict]:
        """
        Get article information
        
        Args:
            article_id: Article ID
            
        Returns:
            ZhihuContent object or None
        """
        uri = f"/p/{article_id}"
        response_html = await self.get(uri, return_response=True)
        return self._extractor.extract_article_content_from_html(response_html)

    async def get_video_info(self, video_id: str) -> Optional[Dict]:
        """
        Get video information
        
        Args:
            video_id: Video ID
            
        Returns:
            ZhihuContent object or None
        """
        uri = f"/zvideo/{video_id}"
        response_html = await self.get(uri, return_response=True)
        return self._extractor.extract_zvideo_content_from_html(response_html)

    async def close(self):
        """Close browser tab if created by this client"""
        if self.browser_session and self.target_id and self.new_tab:
            try:
                logger.info(f"Close target id: {self.target_id}")
                await self.browser_session.cdp_client.send.Target.closeTarget(params={'targetId': self.target_id})
            except Exception as e:
                logger.warning(f"Error closing target {self.target_id}: {e}")