import random
import time
import os
import json
from typing import Dict, List, Tuple, Optional
from enum import Enum
from urllib.parse import parse_qs, urlparse

try:
    import execjs
    HAS_EXECJS = True
except ImportError:
    HAS_EXECJS = False

try:
    from parsel import Selector
    HAS_PARSEL = True
except ImportError:
    HAS_PARSEL = False


class SearchTime(Enum):
    """Search time range constants"""
    DEFAULT = ""  # Unlimited time
    ONE_DAY = "a_day"  # Within one day
    ONE_WEEK = "a_week"  # Within one week
    ONE_MONTH = "a_month"  # Within one month
    THREE_MONTH = "three_months"  # Within three months
    HALF_YEAR = "half_a_year"  # Within half year
    ONE_YEAR = "a_year"  # Within one year


class SearchType(Enum):
    """Search result type constants"""
    DEFAULT = ""  # All types
    ANSWER = "answer"  # Answers only
    ARTICLE = "article"  # Articles only
    VIDEO = "zvideo"  # Videos only


class SearchSort(Enum):
    """Search result sorting constants"""
    DEFAULT = ""  # General sorting
    UPVOTED_COUNT = "upvoted_count"  # Most upvoted
    CREATE_TIME = "created_time"  # Latest published


def extract_cookies_from_browser(web_cookies: List[Dict]) -> Tuple[str, Dict[str, str]]:
    """Extract and format cookies from browser, filtering only Zhihu related cookies"""
    cookie_dict = {}
    cookie_parts = []
    
    # Zhihu domain patterns to filter
    zhihu_domains = [
        '.zhihu.com',
    ]
    
    for cookie in web_cookies:
        if 'name' in cookie and 'value' in cookie and 'domain' in cookie:
            domain = cookie['domain']
            
            # Filter only Zhihu related cookies
            if any(zhihu_domain in domain for zhihu_domain in zhihu_domains):
                name = cookie['name']
                value = cookie['value']
                cookie_dict[name] = value
                cookie_parts.append(f"{name}={value}")
    
    cookie_string = "; ".join(cookie_parts)
    return cookie_string, cookie_dict


def extract_text_from_html(html_str: str) -> str:
    """Extract text content from HTML string"""
    if not html_str:
        return ""
    
    if not HAS_PARSEL:
        # Simple fallback: remove basic HTML tags
        import re
        text = re.sub(r'<[^>]+>', '', html_str)
        return text.strip()
    
    try:
        selector = Selector(text=html_str)
        text = selector.xpath('string()').get(default="")
        return text.strip()
    except:
        return html_str


def judge_zhihu_url(note_detail_url: str) -> str:
    """
    Judge zhihu url type
    
    Args:
        note_detail_url:
            eg1: https://www.zhihu.com/question/123456789/answer/123456789 # answer
            eg2: https://www.zhihu.com/p/123456789 # article
            eg3: https://www.zhihu.com/zvideo/123456789 # zvideo
    
    Returns:
        Content type string
    """
    if "/answer/" in note_detail_url:
        return "answer"
    elif "/p/" in note_detail_url:
        return "article"
    elif "/zvideo/" in note_detail_url:
        return "zvideo"
    else:
        return ""


class ZhihuError(Exception):
    """Base exception for Zhihu API errors"""
    pass


class NetworkError(ZhihuError):
    """Network connection error"""
    pass


class DataExtractionError(ZhihuError):
    """Data extraction error"""
    pass


class AuthenticationError(ZhihuError):
    """Authentication error"""
    pass


class RateLimitError(ZhihuError):
    """Rate limit exceeded error"""
    pass


class VerificationError(ZhihuError):
    """Account verification required error"""
    pass


def sign(url: str, cookies: str) -> Dict:
    """
    Zhihu sign algorithm using zhihu.js in the same directory
    
    Args:
        url: Request URL with query string
        cookies: Request cookies with d_c0 key
    
    Returns:
        Dictionary with x-zst-81 and x-zse-96 signatures
    """
    if not HAS_EXECJS:
        return {"x-zst-81": "", "x-zse-96": ""}
    
    try:
        # Load the zhihu.js file from the same directory
        js_file_path = os.path.join(os.path.dirname(__file__), 'zhihu.js')
        
        if not os.path.exists(js_file_path):
            return {"x-zst-81": "", "x-zse-96": ""}
        
        with open(js_file_path, mode="r", encoding="utf-8-sig") as f:
            js_content = f.read()
        
        js_context = execjs.compile(js_content)
        sign_result = js_context.call("get_sign", url, cookies)
        return sign_result
    except Exception as e:
        return {"x-zst-81": "", "x-zse-96": ""}


# Zhihu constants
ZHIHU_URL = "https://www.zhihu.com"
ZHIHU_ZHUANLAN_URL = "https://zhuanlan.zhihu.com"
ANSWER_NAME = "answer"
ARTICLE_NAME = "article"
VIDEO_NAME = "zvideo"


class ZhihuContent:
    """Zhihu content data model"""
    def __init__(self):
        self.content_id = ""
        self.content_type = ""
        self.content_text = ""
        self.content_url = ""
        self.title = ""
        self.desc = ""
        self.created_time = 0
        self.updated_time = 0
        self.voteup_count = 0
        self.comment_count = 0
        self.question_id = ""
        self.user_id = ""
        self.user_link = ""
        self.user_nickname = ""
        self.user_avatar = ""
        self.user_url_token = ""


class ZhihuComment:
    """Zhihu comment data model"""
    def __init__(self):
        self.comment_id = ""
        self.parent_comment_id = ""
        self.content = ""
        self.publish_time = 0
        self.ip_location = ""
        self.sub_comment_count = 0
        self.like_count = 0
        self.dislike_count = 0
        self.content_id = ""
        self.content_type = ""
        self.user_id = ""
        self.user_link = ""
        self.user_nickname = ""
        self.user_avatar = ""


class ZhihuCreator:
    """Zhihu creator data model"""
    def __init__(self):
        self.user_id = ""
        self.user_link = ""
        self.user_nickname = ""
        self.user_avatar = ""
        self.url_token = ""
        self.gender = ""
        self.ip_location = ""
        self.follows = 0
        self.fans = 0
        self.anwser_count = 0
        self.video_count = 0
        self.question_count = 0
        self.article_count = 0
        self.column_count = 0
        self.get_voteup_count = 0


class ZhihuExtractor:
    """Zhihu content extractor"""
    
    def __init__(self):
        pass

    def extract_contents_from_search(self, json_data: Dict) -> List[Dict]:
        """Extract zhihu contents from search results"""
        if not json_data:
            return []

        search_result: List[Dict] = json_data.get("data", [])
        search_result = [s_item for s_item in search_result if s_item.get("type") in ['search_result', 'zvideo']]
        return self._extract_content_list([sr_item.get("object") for sr_item in search_result if sr_item.get("object")])

    def _extract_content_list(self, content_list: List[Dict]) -> List[Dict]:
        """Extract zhihu content list"""
        if not content_list:
            return []

        res: List[Dict] = []
        for content in content_list:
            if content.get("type") == ANSWER_NAME:
                res.append(self._extract_answer_content(content))
            elif content.get("type") == ARTICLE_NAME:
                res.append(self._extract_article_content(content))
            elif content.get("type") == VIDEO_NAME:
                res.append(self._extract_zvideo_content(content))
            else:
                continue
        return res

    def _extract_answer_content(self, answer: Dict) -> Dict:
        """Extract zhihu answer content"""
        content_id = str(answer.get("id", ""))
        question_id = str(answer.get("question", {}).get("id", ""))
        author_info = self._extract_content_or_comment_author(answer.get("author"))
        
        return {
            "content_id": content_id,
            "content_type": answer.get("type", ""),
            "content_text": extract_text_from_html(answer.get("content", "")),
            "question_id": question_id,
            "content_url": f"{ZHIHU_URL}/question/{question_id}/answer/{content_id}",
            "title": extract_text_from_html(answer.get("title", "")),
            "desc": extract_text_from_html(answer.get("description", "") or answer.get("excerpt", "")),
            "created_time": answer.get("created_time", 0),
            "updated_time": answer.get("updated_time", 0),
            "voteup_count": answer.get("voteup_count", 0),
            "comment_count": answer.get("comment_count", 0),
            "user_id": author_info["user_id"],
            "user_link": author_info["user_link"],
            "user_nickname": author_info["user_nickname"],
            "user_avatar": author_info["user_avatar"],
            "user_url_token": author_info["url_token"],
        }

    def _extract_article_content(self, article: Dict) -> Dict:
        """Extract zhihu article content"""
        content_id = str(article.get("id", ""))
        author_info = self._extract_content_or_comment_author(article.get("author"))
        
        return {
            "content_id": content_id,
            "content_type": article.get("type", ""),
            "content_text": extract_text_from_html(article.get("content", "")),
            "content_url": f"{ZHIHU_ZHUANLAN_URL}/p/{content_id}",
            "title": extract_text_from_html(article.get("title", "")),
            "desc": extract_text_from_html(article.get("excerpt", "")),
            "created_time": article.get("created_time", 0) or article.get("created", 0),
            "updated_time": article.get("updated_time", 0) or article.get("updated", 0),
            "voteup_count": article.get("voteup_count", 0),
            "comment_count": article.get("comment_count", 0),
            "user_id": author_info["user_id"],
            "user_link": author_info["user_link"],
            "user_nickname": author_info["user_nickname"],
            "user_avatar": author_info["user_avatar"],
            "user_url_token": author_info["url_token"],
        }

    def _extract_zvideo_content(self, zvideo: Dict) -> Dict:
        """Extract zhihu zvideo content"""
        content_id = str(zvideo.get("id", ""))
        
        if "video" in zvideo and isinstance(zvideo.get("video"), dict):
            content_url = f"{ZHIHU_URL}/zvideo/{content_id}"
            created_time = zvideo.get("published_at", 0)
            updated_time = zvideo.get("updated_at", 0)
        else:
            content_url = zvideo.get("video_url", "")
            created_time = zvideo.get("created_at", 0)
            updated_time = 0
        
        author_info = self._extract_content_or_comment_author(zvideo.get("author"))
        
        return {
            "content_id": content_id,
            "content_type": zvideo.get("type", ""),
            "content_url": content_url,
            "title": extract_text_from_html(zvideo.get("title", "")),
            "desc": extract_text_from_html(zvideo.get("description", "")),
            "created_time": created_time,
            "updated_time": updated_time,
            "voteup_count": zvideo.get("voteup_count", 0),
            "comment_count": zvideo.get("comment_count", 0),
            "user_id": author_info["user_id"],
            "user_link": author_info["user_link"],
            "user_nickname": author_info["user_nickname"],
            "user_avatar": author_info["user_avatar"],
            "user_url_token": author_info["url_token"],
        }

    @staticmethod
    def _extract_content_or_comment_author(author: Dict) -> Dict:
        """Extract zhihu author"""
        try:
            if not author:
                return {
                    "user_id": "",
                    "user_link": "",
                    "user_nickname": "",
                    "user_avatar": "",
                    "url_token": "",
                }
            if not author.get("id"):
                author = author.get("member", {})
            
            url_token = author.get("url_token", "")
            return {
                "user_id": str(author.get("id", "")),
                "user_link": f"{ZHIHU_URL}/people/{url_token}",
                "user_nickname": author.get("name", ""),
                "user_avatar": author.get("avatar_url", ""),
                "url_token": url_token,
            }
        except Exception as e:
            return {
                "user_id": "",
                "user_link": "",
                "user_nickname": "",
                "user_avatar": "",
                "url_token": "",
            }

    def extract_comments(self, content_dict: Dict, comments: List[Dict]) -> List[Dict]:
        """Extract zhihu comments"""
        if not comments:
            return []
        res: List[Dict] = []
        for comment in comments:
            if comment.get("type") != "comment":
                continue
            res.append(self._extract_comment(content_dict, comment))
        return res

    def _extract_comment(self, content_dict: Dict, comment: Dict) -> Dict:
        """Extract zhihu comment"""
        author_info = self._extract_content_or_comment_author(comment.get("author"))
        
        return {
            "comment_id": str(comment.get("id", "")),
            "parent_comment_id": str(comment.get("reply_comment_id", "")),
            "content": extract_text_from_html(comment.get("content", "")),
            "publish_time": comment.get("created_time", 0),
            "ip_location": self._extract_comment_ip_location(comment.get("comment_tag", [])),
            "sub_comment_count": comment.get("child_comment_count", 0),
            "like_count": comment.get("like_count", 0),
            "dislike_count": comment.get("dislike_count", 0),
            "content_id": content_dict.get("content_id", ""),
            "content_type": content_dict.get("content_type", ""),
            "user_id": author_info["user_id"],
            "user_link": author_info["user_link"],
            "user_nickname": author_info["user_nickname"],
            "user_avatar": author_info["user_avatar"],
        }

    @staticmethod
    def _extract_comment_ip_location(comment_tags: List[Dict]) -> str:
        """Extract comment ip location"""
        if not comment_tags:
            return ""

        for ct in comment_tags:
            if ct.get("type") == "ip_info":
                return ct.get("text", "")

        return ""

    @staticmethod
    def extract_offset(paging_info: Dict) -> str:
        """Extract offset from paging info"""
        next_url = paging_info.get("next", "")
        if not next_url:
            return ""

        parsed_url = urlparse(next_url)
        query_params = parse_qs(parsed_url.query)
        offset = query_params.get('offset', [""])[0]
        return offset

    @staticmethod
    def _format_gender_text(gender: int) -> str:
        """Format gender text"""
        if gender == 1:
            return "男"
        elif gender == 0:
            return "女"
        else:
            return "未知"

    def extract_creator(self, user_url_token: str, html_content: str) -> Optional[Dict]:
        """Extract zhihu creator"""
        if not html_content or not HAS_PARSEL:
            return None

        js_init_data = Selector(text=html_content).xpath("//script[@id='js-initialData']/text()").get(default="").strip()
        if not js_init_data:
            return None

        js_init_data_dict: Dict = json.loads(js_init_data)
        users_info: Dict = js_init_data_dict.get("initialState", {}).get("entities", {}).get("users", {})
        if not users_info:
            return None

        creator_info: Dict = users_info.get(user_url_token)
        if not creator_info:
            return None

        return {
            "user_id": str(creator_info.get("id", "")),
            "user_link": f"{ZHIHU_URL}/people/{user_url_token}",
            "user_nickname": creator_info.get("name", ""),
            "user_avatar": creator_info.get("avatarUrl", ""),
            "url_token": creator_info.get("urlToken", "") or user_url_token,
            "gender": self._format_gender_text(creator_info.get("gender", -1)),
            "ip_location": creator_info.get("ipInfo", ""),
            "follows": creator_info.get("followingCount", 0),
            "fans": creator_info.get("followerCount", 0),
            "anwser_count": creator_info.get("answerCount", 0),
            "video_count": creator_info.get("zvideoCount", 0),
            "question_count": creator_info.get("questionCount", 0),
            "article_count": creator_info.get("articlesCount", 0),
            "column_count": creator_info.get("columnsCount", 0),
            "get_voteup_count": creator_info.get("voteupCount", 0),
        }

    def extract_content_list_from_creator(self, answer_list: List[Dict]) -> List[Dict]:
        """Extract content list from creator"""
        if not answer_list:
            return []
        return self._extract_content_list(answer_list)

    def extract_answer_content_from_html(self, html_content: str) -> Optional[Dict]:
        """Extract zhihu answer content from html"""
        if not HAS_PARSEL:
            return None
            
        js_init_data: str = Selector(text=html_content).xpath("//script[@id='js-initialData']/text()").get(default="")
        if not js_init_data:
            return None
        json_data: Dict = json.loads(js_init_data)
        answer_info: Dict = json_data.get("initialState", {}).get("entities", {}).get("answers", {})
        if not answer_info:
            return None

        return self._extract_answer_content(answer_info.get(list(answer_info.keys())[0]))

    def extract_article_content_from_html(self, html_content: str) -> Optional[Dict]:
        """Extract zhihu article content from html"""
        if not HAS_PARSEL:
            return None
            
        js_init_data: str = Selector(text=html_content).xpath("//script[@id='js-initialData']/text()").get(default="")
        if not js_init_data:
            return None
        json_data: Dict = json.loads(js_init_data)
        article_info: Dict = json_data.get("initialState", {}).get("entities", {}).get("articles", {})
        if not article_info:
            return None

        return self._extract_article_content(article_info.get(list(article_info.keys())[0]))

    def extract_zvideo_content_from_html(self, html_content: str) -> Optional[Dict]:
        """Extract zhihu zvideo content from html"""
        if not HAS_PARSEL:
            return None
            
        js_init_data: str = Selector(text=html_content).xpath("//script[@id='js-initialData']/text()").get(default="")
        if not js_init_data:
            return None
        json_data: Dict = json.loads(js_init_data)
        zvideo_info: Dict = json_data.get("initialState", {}).get("entities", {}).get("zvideos", {})
        users: Dict = json_data.get("initialState", {}).get("entities", {}).get("users", {})
        if not zvideo_info:
            return None

        # Handle user info and video info
        video_detail_info: Dict = zvideo_info.get(list(zvideo_info.keys())[0])
        if not video_detail_info:
            return None
        if isinstance(video_detail_info.get("author"), str):
            author_name: str = video_detail_info.get("author")
            video_detail_info["author"] = users.get(author_name)

        return self._extract_zvideo_content(video_detail_info)