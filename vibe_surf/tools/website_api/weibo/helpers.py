import pdb
import random
import time
import re
import json
import html
from typing import Dict, List, Tuple, Optional
from enum import Enum
from urllib.parse import parse_qs, unquote


class SearchType(Enum):
    """Search type enumeration for Weibo"""
    DEFAULT = "1"
    REAL_TIME = "61"
    POPULAR = "60"
    VIDEO = "64"


class TrendingType(Enum):
    """Trending type enumeration for Weibo mobile APIs"""
    TRENDING_LIST = "trending_list"
    HOT_POSTS = "hot_posts"


class TrendingConstants:
    """Constants for Weibo mobile trending APIs"""
    # Trending list API
    TRENDING_CONTAINER_ID = "102803_ctg1_8999_-_ctg1_8999_home"
    
    # Hot posts API
    HOT_POSTS_CONTAINER_ID = "102803"
    
    # Common parameters
    OPEN_APP = "0"


def generate_device_id() -> str:
    """Generate a random device ID for Weibo requests"""
    chars = "0123456789abcdef"
    return ''.join(random.choices(chars, k=32))


def create_container_id(search_type: SearchType, keyword: str) -> str:
    """Create container ID for search requests"""
    return f"100103type={search_type.value}&q={keyword}"


def extract_cookies_from_browser(web_cookies: List[Dict]) -> Tuple[str, Dict[str, str]]:
    """Extract and format cookies from browser, filtering only Weibo related cookies"""
    cookie_dict = {}
    cookie_parts = []
    
    # Weibo domain patterns to filter
    weibo_domains = [
        # '.weibo.com',
        '.weibo.cn',
        # 'm.weibo.cn',
        # 'www.weibo.com'
    ]
    for cookie in web_cookies:
        if 'name' in cookie and 'value' in cookie and 'domain' in cookie:
            domain = cookie['domain']
            
            # Filter only Weibo related cookies
            if any(wb_domain in domain for wb_domain in weibo_domains):
                name = cookie['name']
                value = cookie['value']
                cookie_dict[name] = value
                cookie_parts.append(f"{name}={value}")
    
    cookie_string = "; ".join(cookie_parts)
    return cookie_string, cookie_dict


def extract_mid_from_url(weibo_url: str) -> Optional[str]:
    """Extract mid from Weibo URL"""
    patterns = [
        r'/detail/(\w+)',
        r'mid=(\w+)',
        r'/(\w+)$',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, weibo_url)
        if match:
            return match.group(1)
    
    return None


def extract_user_id_from_url(user_url: str) -> Optional[str]:
    """Extract user ID from Weibo user URL"""
    patterns = [
        r'/u/(\d+)',
        r'uid=(\d+)',
        r'/profile/(\d+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, user_url)
        if match:
            return match.group(1)
    
    return None


def parse_weibo_time(time_str: str) -> Optional[int]:
    """Parse Weibo time string to timestamp"""
    if not time_str:
        return None
        
    try:
        # Handle relative time like "3分钟前", "1小时前", etc.
        if "分钟前" in time_str:
            minutes = int(re.search(r'(\d+)分钟前', time_str).group(1))
            return int(time.time()) - minutes * 60
        elif "小时前" in time_str:
            hours = int(re.search(r'(\d+)小时前', time_str).group(1))
            return int(time.time()) - hours * 3600
        elif "天前" in time_str:
            days = int(re.search(r'(\d+)天前', time_str).group(1))
            return int(time.time()) - days * 86400
        elif "今天" in time_str:
            return int(time.time())
        elif "昨天" in time_str:
            return int(time.time()) - 86400
        else:
            # Try to parse as timestamp
            return int(time_str)
    except (ValueError, AttributeError):
        return None


def extract_image_urls(pics: List[Dict]) -> List[str]:
    """Extract image URLs from Weibo pics data"""
    image_urls = []
    
    for pic in pics:
        if isinstance(pic, dict):
            # Try different URL fields
            url = pic.get('url') or pic.get('large', {}).get('url') or pic.get('pic_big')
            if url:
                image_urls.append(url)
    
    return image_urls


def process_weibo_text(text: str) -> str:
    """Process Weibo text content, remove HTML tags and clean up"""
    if not text:
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def validate_weibo_data(weibo_data: Dict) -> bool:
    """Validate if weibo data contains required fields"""
    required_fields = ["id", "text", "user"]
    
    for field in required_fields:
        if field not in weibo_data:
            return False
    
    return True


def filter_search_result_card(card_list: List[Dict]) -> List[Dict]:
    """
    Filter Weibo search results, only keep card_type=9 data
    """
    note_list: List[Dict] = []
    
    for card_item in card_list:
        if card_item.get("card_type") == 9:
            note_list.append(card_item)
            
        # Check card_group for nested items
        card_group = card_item.get("card_group", [])
        for card_group_item in card_group:
            if card_group_item.get("card_type") == 9:
                note_list.append(card_group_item)

    return note_list


def extract_container_params(m_weibocn_params: str) -> Dict[str, str]:
    """Extract container parameters from M_WEIBOCN_PARAMS cookie"""
    try:
        params_dict = parse_qs(unquote(m_weibocn_params))
        return {
            "fid_container_id": params_dict.get("fid", [""])[0],
            "lfid_container_id": params_dict.get("lfid", [""])[0]
        }
    except Exception:
        return {"fid_container_id": "", "lfid_container_id": ""}


def build_image_proxy_url(image_url: str, proxy_host: str = "https://i1.wp.com/") -> str:
    """Build proxied image URL to bypass anti-hotlinking"""
    if not image_url.startswith("http"):
        return image_url
    
    # Remove https:// prefix
    clean_url = image_url[8:] if image_url.startswith("https://") else image_url[7:]
    
    # Split URL parts
    url_parts = clean_url.split("/")
    
    # Reconstruct URL with 'large' for high quality images
    processed_url = ""
    for i, part in enumerate(url_parts):
        if i == 1:  # Insert 'large' after domain
            processed_url += "large/"
        elif i == len(url_parts) - 1:  # Last part (filename)
            processed_url += part
        else:
            processed_url += part + "/"
    
    return f"{proxy_host}{processed_url}"


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for file system"""
    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Remove extra spaces
    filename = re.sub(r'\s+', ' ', filename).strip()
    # Limit length
    if len(filename) > 100:
        filename = filename[:100]
    
    return filename or "untitled"


def extract_render_data(html_content: str) -> Optional[Dict]:
    """Extract render data from Weibo detail page HTML"""
    try:
        match = re.search(r'var \$render_data = (\[.*?\])\[0\]', html_content, re.DOTALL)
        if match:
            render_data_json = match.group(1)
            render_data_dict = json.loads(render_data_json)
            return render_data_dict[0] if render_data_dict else None
    except (json.JSONDecodeError, IndexError):
        pass
    
    return None


class WeiboError(Exception):
    """Base exception for Weibo API errors"""
    pass


class NetworkError(WeiboError):
    """Network connection error"""
    pass


class DataExtractionError(WeiboError):
    """Data extraction error"""
    pass


class AuthenticationError(WeiboError):
    """Authentication error"""
    pass


class RateLimitError(WeiboError):
    """Rate limit exceeded error"""
    pass


class ContentNotFoundError(WeiboError):
    """Content not found error"""
    pass


class ValidationError(WeiboError):
    """Data validation error"""
    pass

def extract_redirect_url_from_html(html_content: str) -> Optional[str]:
    """Extract redirect URL from HTML meta refresh or JavaScript redirect"""
    try:
        # Try meta refresh tag
        meta_match = re.search(r'<meta[^>]*http-equiv=["\']refresh["\'][^>]*content=["\'][^"\']*url=([^"\']+)["\']', html_content, re.IGNORECASE)
        if meta_match:
            return html.unescape(meta_match.group(1))
        
        # Try JavaScript location.replace
        js_match = re.search(r'location\.replace\(["\']([^"\']+)["\']\)', html_content, re.IGNORECASE)
        if js_match:
            return html.unescape(js_match.group(1))
        
        # Try window.location.href
        js_match2 = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', html_content, re.IGNORECASE)
        if js_match2:
            return html.unescape(js_match2.group(1))
            
    except Exception:
        pass
    
    return None


def decode_chinese_html(html_content: bytes) -> str:
    """Decode HTML content that might be in GBK or other Chinese encodings"""
    encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'big5']
    
    for encoding in encodings:
        try:
            return html_content.decode(encoding)
        except UnicodeDecodeError:
            continue
    
    # If all else fails, try with error handling
    return html_content.decode('utf-8', errors='ignore')


def get_mobile_user_agent() -> str:
    ua_list = [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPad; CPU OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/114.0.5735.99 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPad; CPU OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/114.0.5735.124 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; SAMSUNG SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/21.0 Chrome/110.0.5481.154 Mobile Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36 OPR/99.0.0.0",
        "Mozilla/5.0 (Linux; Android 10; JNY-LX1; HMSCore 6.11.0.302) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.88 HuaweiBrowser/13.0.5.303 Mobile Safari/537.36"
    ]
    return random.choice(ua_list)


def transform_weibo_post_data(card_data: Dict) -> Optional[Dict]:
    """
    Transform raw Weibo card data into structured post information
    
    Args:
        card_data: Raw card data from Weibo API
        
    Returns:
        Structured post information or None if invalid data
    """
    if not isinstance(card_data, dict) or card_data.get("card_type") != 9:
        return None
    
    mblog = card_data.get("mblog", {})
    if not mblog:
        return None
    
    user = mblog.get("user", {})
    if not user:
        return None
    
    try:
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
        
        # Clean up followers_count if it's a string with suffix
        followers_count = user.get("followers_count", 0)
        if isinstance(followers_count, str):
            # Handle cases like "11.2万"
            if "万" in followers_count:
                try:
                    num_str = followers_count.replace("万", "")
                    post_info["user"]["followers_count"] = int(float(num_str) * 10000)
                except (ValueError, TypeError):
                    post_info["user"]["followers_count"] = 0
            else:
                try:
                    post_info["user"]["followers_count"] = int(followers_count)
                except (ValueError, TypeError):
                    post_info["user"]["followers_count"] = 0
        
        # Validate essential fields
        if not post_info["mid"] or not post_info["user"]["id"]:
            return None
            
        return post_info
        
    except Exception as e:
        # Log error but don't fail completely
        return None


def transform_weibo_search_results(api_response: Dict) -> List[Dict]:
    """
    Transform raw Weibo search API response into list of structured posts
    
    Args:
        api_response: Raw API response from search_posts_by_keyword
        
    Returns:
        List of structured post information
    """
    if not isinstance(api_response, dict):
        return []
    
    cards = api_response.get("cards", [])
    if not isinstance(cards, list):
        return []
    
    # Filter and transform cards
    filtered_cards = filter_search_result_card(cards)
    structured_posts = []
    
    for card in filtered_cards:
        post_info = transform_weibo_post_data(card)
        if post_info:
            structured_posts.append(post_info)
    
    return structured_posts


def transform_weibo_post_detail(detail_response: Dict) -> Optional[Dict]:
    """
    Transform raw Weibo post detail response into structured post information
    
    Args:
        detail_response: Raw response from get_post_detail
        
    Returns:
        Structured post detail information or None if invalid data
    """
    if not isinstance(detail_response, dict):
        return None
    
    mblog = detail_response.get("mblog", {})
    if not mblog:
        return None
    
    user = mblog.get("user", {})
    if not user:
        return None
    
    try:
        post_detail = {
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
                "friends_count": user.get("follow_count", 0),  # Note: different field name
                "statuses_count": user.get("statuses_count", 0),
                "verified": user.get("verified", False),
                "verified_type": user.get("verified_type", 0),
                "verified_reason": user.get("verified_reason", ""),
                "description": user.get("description", ""),
            },
            "pics": mblog.get("pic_ids", []),
            "pic_num": mblog.get("pic_num", 0),
            "page_info": mblog.get("page_info", {}),  # Video info if present
            "is_long_text": mblog.get("isLongText", False),
            "favorited": mblog.get("favorited", False),
            "can_edit": mblog.get("can_edit", False),
            "visible": mblog.get("visible", {}),
            "bid": mblog.get("bid", ""),
            "status_title": mblog.get("status_title", ""),
        }
        
        # Clean up followers_count if it's a string with suffix
        followers_count = user.get("followers_count", 0)
        if isinstance(followers_count, str):
            # Handle cases like "3800.8万"
            if "万" in followers_count:
                try:
                    num_str = followers_count.replace("万", "")
                    post_detail["user"]["followers_count"] = int(float(num_str) * 10000)
                except (ValueError, TypeError):
                    post_detail["user"]["followers_count"] = 0
            else:
                try:
                    post_detail["user"]["followers_count"] = int(followers_count)
                except (ValueError, TypeError):
                    post_detail["user"]["followers_count"] = 0
        
        # Process video information if present
        page_info = mblog.get("page_info", {})
        if page_info and page_info.get("type") == "video":
            post_detail["video_info"] = {
                "title": page_info.get("title", ""),
                "page_title": page_info.get("page_title", ""),
                "object_id": page_info.get("object_id", ""),
                "page_url": page_info.get("page_url", ""),
                "duration": page_info.get("media_info", {}).get("duration", 0),
                "video_orientation": page_info.get("video_orientation", ""),
                "urls": page_info.get("urls", {}),
                "cover_image": {
                    "url": page_info.get("page_pic", {}).get("url", ""),
                    "width": page_info.get("page_pic", {}).get("width", ""),
                    "height": page_info.get("page_pic", {}).get("height", ""),
                }
            }
        
        # Validate essential fields
        if not post_detail["mid"] or not post_detail["user"]["id"]:
            return None
            
        return post_detail
        
    except Exception as e:
        # Log error but don't fail completely
        return None


def transform_weibo_comment_data(comment_data: Dict) -> Optional[Dict]:
    """
    Transform raw Weibo comment data into structured comment information
    
    Args:
        comment_data: Raw comment data from Weibo API
        
    Returns:
        Structured comment information or None if invalid data
    """
    if not isinstance(comment_data, dict):
        return None
    
    user = comment_data.get("user", {})
    if not user:
        return None
    
    try:
        comment_info = {
            "id": comment_data.get("id"),
            "text": process_weibo_text(comment_data.get("text", "")),
            "created_at": comment_data.get("created_at"),
            "source": comment_data.get("source"),
            "floor_number": comment_data.get("floor_number", 0),
            "like_count": comment_data.get("like_count", 0),
            "liked": comment_data.get("liked", False),
            "user": {
                "id": user.get("id"),
                "screen_name": user.get("screen_name"),
                "profile_image_url": user.get("profile_image_url"),
                "followers_count": user.get("followers_count", 0),
                "follow_count": user.get("follow_count", 0),
                "statuses_count": user.get("statuses_count", 0),
                "verified": user.get("verified", False),
                "verified_type": user.get("verified_type", -1),
                "verified_reason": user.get("verified_reason", ""),
                "description": user.get("description", ""),
                "gender": user.get("gender", ""),
            },
            "rootid": comment_data.get("rootid"),
            "disable_reply": comment_data.get("disable_reply", 0),
            "isLikedByMblogAuthor": comment_data.get("isLikedByMblogAuthor", False),
            "bid": comment_data.get("bid", ""),
            # Sub-comments information
            "has_sub_comments": comment_data.get("comments", False),
            "sub_comments_count": comment_data.get("total_number", 0),
        }
        
        # Clean up followers_count if it's a string with suffix
        followers_count = user.get("followers_count", 0)
        if isinstance(followers_count, str):
            # Handle cases like "115", "11万", etc.
            if "万" in followers_count:
                try:
                    num_str = followers_count.replace("万", "")
                    comment_info["user"]["followers_count"] = int(float(num_str) * 10000)
                except (ValueError, TypeError):
                    comment_info["user"]["followers_count"] = 0
            else:
                try:
                    comment_info["user"]["followers_count"] = int(followers_count)
                except (ValueError, TypeError):
                    comment_info["user"]["followers_count"] = 0
        
        # Validate essential fields
        if not comment_info["id"] or not comment_info["user"]["id"]:
            return None
            
        return comment_info
        
    except Exception as e:
        # Log error but don't fail completely
        return None


def transform_weibo_comments_response(comments_response: Dict) -> List[Dict]:
    """
    Transform raw Weibo comments API response into list of structured comments
    
    Args:
        comments_response: Raw API response from get_post_comments
        
    Returns:
        List of structured comment information
    """
    if not isinstance(comments_response, dict):
        return []
    
    comments_data = comments_response.get("data", [])
    if not isinstance(comments_data, list):
        return []
    
    structured_comments = []
    
    for comment in comments_data:
        comment_info = transform_weibo_comment_data(comment)
        if comment_info:
            structured_comments.append(comment_info)
    
    return structured_comments


def transform_weibo_user_info(user_response: Dict) -> Optional[Dict]:
    """
    Transform raw Weibo user info response into structured user information
    
    Args:
        user_response: Raw response from get_user_info
        
    Returns:
        Structured user information or None if invalid data
    """
    if not isinstance(user_response, dict):
        return None
    
    user = user_response.get("user", {})
    if not user or not user.get("id"):
        return None
    
    try:
        user_info = {
            "id": user.get("id"),
            "screen_name": user.get("screen_name", ""),
            "profile_image_url": user.get("profile_image_url", ""),
            "followers_count": user.get("followers_count", 0),
            "friends_count": user.get("friends_count", 0),
            "statuses_count": user.get("statuses_count", 0),
            "verified": user.get("verified", False),
            "verified_type": user.get("verified_type", -1),
            "verified_reason": user.get("verified_reason", ""),
            "description": user.get("description", ""),
            "gender": user.get("gender", ""),
            "location": user.get("location", ""),
            "created_at": user.get("created_at", ""),
            "profile_url": user.get("profile_url", ""),
            "cover_image_phone": user.get("cover_image_phone", ""),
            "avatar_hd": user.get("avatar_hd", ""),
            # Container and navigation info
            "containerid": user_response.get("containerid", ""),
            "tabs_info": {
                "selected_tab": user_response.get("tabsInfo", {}).get("selectedTab", 1),
                "tabs": []
            }
        }
        
        # Process tabs information
        tabs = user_response.get("tabsInfo", {}).get("tabs", [])
        for tab in tabs:
            if isinstance(tab, dict):
                tab_info = {
                    "id": tab.get("id"),
                    "tab_key": tab.get("tabKey", ""),
                    "title": tab.get("title", ""),
                    "tab_type": tab.get("tab_type", ""),
                    "containerid": tab.get("containerid", ""),
                    "must_show": tab.get("must_show", 0),
                    "hidden": tab.get("hidden", 0),
                }
                
                # Add optional fields if present
                if "apipath" in tab:
                    tab_info["apipath"] = tab["apipath"]
                if "headSubTitleText" in tab:
                    tab_info["head_subtitle_text"] = tab["headSubTitleText"]
                if "tab_icon" in tab:
                    tab_info["tab_icon"] = tab["tab_icon"]
                if "tab_icon_dark" in tab:
                    tab_info["tab_icon_dark"] = tab["tab_icon_dark"]
                if "url" in tab:
                    tab_info["url"] = tab["url"]
                
                user_info["tabs_info"]["tabs"].append(tab_info)
        
        # Clean up followers_count if it's a string with suffix
        followers_count = user.get("followers_count", 0)
        if isinstance(followers_count, str):
            if "万" in followers_count:
                try:
                    num_str = followers_count.replace("万", "")
                    user_info["followers_count"] = int(float(num_str) * 10000)
                except (ValueError, TypeError):
                    user_info["followers_count"] = 0
            else:
                try:
                    user_info["followers_count"] = int(followers_count)
                except (ValueError, TypeError):
                    user_info["followers_count"] = 0
        
        return user_info
        
    except Exception as e:
        # Log error but don't fail completely
        return None


def transform_weibo_user_posts_response(user_posts_response: Dict) -> Optional[Dict]:
    """
    Transform raw Weibo user posts response into structured information
    
    Args:
        user_posts_response: Raw response from get_user_posts
        
    Returns:
        Structured user posts information or None if invalid data
    """
    if not isinstance(user_posts_response, dict):
        return None
    
    user_info = user_posts_response.get("userInfo", {})
    if not user_info:
        return None
    
    try:
        user_posts_info = {
            "user": {
                "id": user_info.get("id"),
                "screen_name": user_info.get("screen_name", ""),
                "profile_image_url": user_info.get("profile_image_url", ""),
                "followers_count": user_info.get("followers_count", 0),
                "follow_count": user_info.get("follow_count", 0),
                "statuses_count": user_info.get("statuses_count", 0),
                "verified": user_info.get("verified", False),
                "verified_type": user_info.get("verified_type", -1),
                "verified_reason": user_info.get("verified_reason", ""),
                "description": user_info.get("description", ""),
                "gender": user_info.get("gender", ""),
                "profile_url": user_info.get("profile_url", ""),
                "cover_image_phone": user_info.get("cover_image_phone", ""),
                "avatar_hd": user_info.get("avatar_hd", ""),
                "mbtype": user_info.get("mbtype", 0),
                "svip": user_info.get("svip", 0),
                "urank": user_info.get("urank", 0),
                "mbrank": user_info.get("mbrank", 0),
            },
            "style_config": {
                "is_video_cover_style": user_posts_response.get("isVideoCoverStyle", 0),
                "is_star_style": user_posts_response.get("isStarStyle", 0),
            },
            "navigation": {
                "fans_scheme": user_posts_response.get("fans_scheme", ""),
                "follow_scheme": user_posts_response.get("follow_scheme", ""),
                "profile_scheme": user_posts_response.get("scheme", ""),
            },
            "tabs_info": {
                "selected_tab": user_posts_response.get("tabsInfo", {}).get("selectedTab", 1),
                "tabs": []
            },
            "toolbar_menus": [],
            "profile_ext": user_posts_response.get("profile_ext", ""),
            "show_app_tips": user_posts_response.get("showAppTips", 0),
            # Posts data if present
            "posts": [],
            "pagination": {
                "since_id": user_posts_response.get("cardlistInfo", {}).get("since_id", ""),
                "total": user_posts_response.get("cardlistInfo", {}).get("total", 0),
            }
        }
        
        # Process tabs information
        tabs = user_posts_response.get("tabsInfo", {}).get("tabs", [])
        for tab in tabs:
            if isinstance(tab, dict):
                tab_info = {
                    "id": tab.get("id"),
                    "tab_key": tab.get("tabKey", ""),
                    "title": tab.get("title", ""),
                    "tab_type": tab.get("tab_type", ""),
                    "containerid": tab.get("containerid", ""),
                    "must_show": tab.get("must_show", 0),
                    "hidden": tab.get("hidden", 0),
                }
                
                # Add optional fields if present
                if "apipath" in tab:
                    tab_info["apipath"] = tab["apipath"]
                if "headSubTitleText" in tab:
                    tab_info["head_subtitle_text"] = tab["headSubTitleText"]
                if "tab_icon" in tab:
                    tab_info["tab_icon"] = tab["tab_icon"]
                if "tab_icon_dark" in tab:
                    tab_info["tab_icon_dark"] = tab["tab_icon_dark"]
                if "url" in tab:
                    tab_info["url"] = tab["url"]
                
                user_posts_info["tabs_info"]["tabs"].append(tab_info)
        
        # Process toolbar menus
        toolbar_menus = user_info.get("toolbar_menus", [])
        for menu in toolbar_menus:
            if isinstance(menu, dict):
                menu_info = {
                    "type": menu.get("type", ""),
                    "name": menu.get("name", ""),
                    "params": menu.get("params", {}),
                    "scheme": menu.get("scheme", ""),
                }
                user_posts_info["toolbar_menus"].append(menu_info)
        
        # Process posts if present in cards
        cards = user_posts_response.get("cards", [])
        if isinstance(cards, list):
            for card in cards:
                if card.get("card_type") == 9:  # Regular post card
                    post_info = transform_weibo_post_data(card)
                    if post_info:
                        user_posts_info["posts"].append(post_info)
        
        # Clean up followers_count if it's a string with suffix
        followers_count = user_info.get("followers_count", 0)
        if isinstance(followers_count, str):
            if "万" in followers_count:
                try:
                    num_str = followers_count.replace("万", "")
                    user_posts_info["user"]["followers_count"] = int(float(num_str) * 10000)
                except (ValueError, TypeError):
                    user_posts_info["user"]["followers_count"] = 0
            else:
                try:
                    user_posts_info["user"]["followers_count"] = int(followers_count)
                except (ValueError, TypeError):
                    user_posts_info["user"]["followers_count"] = 0
        
        # Validate essential fields
        if not user_posts_info["user"]["id"]:
            return None
            
        return user_posts_info
        
    except Exception as e:
        # Log error but don't fail completely
        return None


def transform_weibo_trending_response(trending_response: Dict) -> List[Dict]:
    """
    Transform raw Weibo trending API response into list of structured posts
    
    Args:
        trending_response: Raw API response from get_trending_list
        
    Returns:
        List of structured post information
    """
    if not isinstance(trending_response, dict):
        return []
    
    statuses = trending_response.get("statuses", [])
    if not isinstance(statuses, list):
        return []
    
    structured_posts = []
    
    for status in statuses:
        post_info = transform_weibo_status_data(status)
        if post_info:
            structured_posts.append(post_info)
    
    return structured_posts


def transform_weibo_status_data(status_data: Dict) -> Optional[Dict]:
    """
    Transform raw Weibo status data into structured post information
    (for trending list and similar direct status responses)
    
    Args:
        status_data: Raw status data from Weibo API
        
    Returns:
        Structured post information or None if invalid data
    """
    if not isinstance(status_data, dict):
        return None
    
    user = status_data.get("user", {})
    if not user:
        return None
    
    try:
        post_info = {
            "mid": status_data.get("id"),
            "text": process_weibo_text(status_data.get("text", "")),
            "created_at": status_data.get("created_at"),
            "source": status_data.get("source"),
            "reposts_count": status_data.get("reposts_count", 0),
            "comments_count": status_data.get("comments_count", 0),
            "attitudes_count": status_data.get("attitudes_count", 0),
            "user": {
                "id": user.get("id"),
                "screen_name": user.get("screen_name"),
                "profile_image_url": user.get("profile_image_url"),
                "followers_count": user.get("followers_count", 0),
                "friends_count": user.get("follow_count", 0),  # Note: different field name
                "statuses_count": user.get("statuses_count", 0),
                "verified": user.get("verified", False),
                "verified_type": user.get("verified_type", 0),
                "verified_reason": user.get("verified_reason", ""),
                "description": user.get("description", ""),
                "gender": user.get("gender", ""),
                "mbtype": user.get("mbtype", 0),
                "svip": user.get("svip", 0),
                "urank": user.get("urank", 0),
                "mbrank": user.get("mbrank", 0),
            },
            "pics": status_data.get("pic_ids", []),
            "pic_num": status_data.get("pic_num", 0),
            "page_info": status_data.get("page_info", {}),  # Video info if present
            "is_long_text": status_data.get("isLongText", False),
            "favorited": status_data.get("favorited", False),
            "can_edit": status_data.get("can_edit", False),
            "visible": status_data.get("visible", {}),
            "bid": status_data.get("bid", ""),
            "mixed_count": status_data.get("mixed_count", 0),
            "pending_approval_count": status_data.get("pending_approval_count", 0),
            "floor_number": status_data.get("floor_number", 0),
        }
        
        # Clean up followers_count if it's a string with suffix
        followers_count = user.get("followers_count", 0)
        if isinstance(followers_count, str):
            # Handle cases like "83.2万"
            if "万" in followers_count:
                try:
                    num_str = followers_count.replace("万", "")
                    post_info["user"]["followers_count"] = int(float(num_str) * 10000)
                except (ValueError, TypeError):
                    post_info["user"]["followers_count"] = 0
            else:
                try:
                    post_info["user"]["followers_count"] = int(followers_count)
                except (ValueError, TypeError):
                    post_info["user"]["followers_count"] = 0
        
        # Process video information if present
        page_info = status_data.get("page_info", {})
        if page_info and page_info.get("type") == "video":
            post_info["video_info"] = {
                "title": page_info.get("title", ""),
                "page_title": page_info.get("page_title", ""),
                "object_id": page_info.get("object_id", ""),
                "page_url": page_info.get("page_url", ""),
                "duration": page_info.get("media_info", {}).get("duration", 0),
                "video_orientation": page_info.get("video_orientation", ""),
                "urls": page_info.get("urls", {}),
                "cover_image": {
                    "url": page_info.get("page_pic", {}).get("url", ""),
                    "width": page_info.get("page_pic", {}).get("width", ""),
                    "height": page_info.get("page_pic", {}).get("height", ""),
                }
            }
        
        # Validate essential fields
        if not post_info["mid"] or not post_info["user"]["id"]:
            return None
            
        return post_info
        
    except Exception as e:
        # Log error but don't fail completely
        return None