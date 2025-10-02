# Disclaimer: This code is for educational and research purposes only. Users should follow these principles:
# 1. Not for any commercial use.
# 2. Follow target platform's terms of service and robots.txt rules.
# 3. No large-scale crawling or operational interference.
# 4. Control request frequency reasonably to avoid unnecessary burden.
# 5. Not for any illegal or inappropriate purposes.
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
    REAL_TIME = "11"
    POPULAR = "12"
    VIDEO = "14"


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