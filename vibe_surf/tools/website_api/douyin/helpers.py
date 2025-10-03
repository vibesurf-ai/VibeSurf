import pdb
import random
import time
import json
import urllib.parse
from typing import Dict, List, Tuple, Optional
from enum import Enum


class SearchChannelType(Enum):
    """Search channel type constants"""
    GENERAL = "aweme_general"  # General content
    VIDEO = "aweme_video_web"  # Video content
    USER = "aweme_user_web"  # User content
    LIVE = "aweme_live"  # Live content


class SearchSortType(Enum):
    """Search sort type constants"""
    GENERAL = 0  # General sorting
    MOST_LIKED = 1  # Most liked
    LATEST = 2  # Latest published


class PublishTimeType(Enum):
    """Publish time type constants"""
    UNLIMITED = 0  # Unlimited
    ONE_DAY = 1  # Within one day
    ONE_WEEK = 7  # Within one week
    SIX_MONTHS = 180  # Within six months


def generate_web_id() -> str:
    """
    Generate random webid for Douyin requests
    
    Returns:
        Random webid string
    """
    def generate_part(t):
        if t is not None:
            return str(t ^ (int(16 * random.random()) >> (t // 4)))
        else:
            return ''.join([
                str(int(1e7)), '-', str(int(1e3)), '-', 
                str(int(4e3)), '-', str(int(8e3)), '-', str(int(1e11))
            ])

    web_id = ''.join(
        generate_part(int(x)) if x in '018' else x for x in generate_part(None)
    )
    return web_id.replace('-', '')[:19]


def generate_trace_id() -> str:
    """Generate a random trace ID for requests"""
    chars = "abcdef0123456789"
    return ''.join(random.choices(chars, k=16))


def create_session_id() -> str:
    """Create a unique session identifier"""
    timestamp = int(time.time() * 1000) << 64
    rand_num = random.randint(0, 2147483646)
    return encode_base36(timestamp + rand_num)


def encode_base36(number: int, alphabet: str = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ') -> str:
    """Convert integer to base36 string"""
    if not isinstance(number, int):
        raise TypeError('Input must be an integer')
    
    if number == 0:
        return alphabet[0]
    
    result = ''
    sign = ''
    
    if number < 0:
        sign = '-'
        number = -number
    
    while number:
        number, remainder = divmod(number, len(alphabet))
        result = alphabet[remainder] + result
    
    return sign + result


def create_common_params() -> Dict[str, any]:
    """
    Create common parameters for Douyin API requests
    
    Returns:
        Dictionary of common parameters
    """
    return {
        "device_platform": "webapp",
        "aid": "6383",
        "channel": "channel_pc_web",
        "version_code": "190600",
        "version_name": "19.6.0",
        "update_version_code": "170400",
        "pc_client_type": "1",
        "cookie_enabled": "true",
        "browser_language": "en-US",
        "browser_platform": "MacIntel",
        "browser_name": "Chrome",
        "browser_version": "125.0.0.0",
        "browser_online": "true",
        "engine_name": "Blink",
        "os_name": "Mac OS",
        "os_version": "10.15.7",
        "cpu_core_num": "8",
        "device_memory": "8",
        "engine_version": "109.0",
        "platform": "PC",
        "screen_width": "1920",
        "screen_height": "1080",
        "effective_type": "4g",
        "round_trip_time": "50",
        "webid": generate_web_id(),
    }


def extract_cookies_from_browser(web_cookies: List[Dict]) -> Tuple[str, Dict[str, str]]:
    """Extract and format cookies from browser, filtering only Douyin related cookies"""
    cookie_dict = {}
    cookie_parts = []
    
    # Douyin domain patterns to filter
    douyin_domains = [
        '.douyin.com',
        # 'www.douyin.com',
        # 'sso.douyin.com'
    ]
    
    for cookie in web_cookies:
        if 'name' in cookie and 'value' in cookie and 'domain' in cookie:
            domain = cookie['domain']
            
            # Filter only Douyin related cookies
            if any(douyin_domain in domain for douyin_domain in douyin_domains):
                name = cookie['name']
                value = cookie['value']
                cookie_dict[name] = value
                cookie_parts.append(f"{name}={value}")
    cookie_string = "; ".join(cookie_parts)
    return cookie_string, cookie_dict


def create_referer_url(keyword: str = "", aweme_id: str = "") -> str:
    """
    Create appropriate referer URL for Douyin requests
    
    Args:
        keyword: Search keyword if applicable
        aweme_id: Aweme ID if applicable
        
    Returns:
        Referer URL string
    """
    if keyword:
        return f"https://www.douyin.com/search/{urllib.parse.quote(keyword)}"
    elif aweme_id:
        return f"https://www.douyin.com/video/{aweme_id}"
    else:
        return "https://www.douyin.com/"


def extract_aweme_media_urls(aweme_data: Dict) -> Dict[str, List[str]]:
    """
    Extract media URLs from aweme data
    
    Args:
        aweme_data: Aweme item data
        
    Returns:
        Dictionary containing image and video URLs
    """
    result = {
        "images": [],
        "videos": [],
        "cover": ""
    }
    
    try:
        # Extract images if available
        if "images" in aweme_data:
            for img in aweme_data["images"]:
                if "url_list" in img and img["url_list"]:
                    result["images"].append(img["url_list"][0])
        
        # Extract video URL
        if "video" in aweme_data and "play_addr" in aweme_data["video"]:
            play_addr = aweme_data["video"]["play_addr"]
            if "url_list" in play_addr and play_addr["url_list"]:
                result["videos"].append(play_addr["url_list"][0])
        
        # Extract cover image
        if "video" in aweme_data and "cover" in aweme_data["video"]:
            cover_data = aweme_data["video"]["cover"]
            if "url_list" in cover_data and cover_data["url_list"]:
                result["cover"] = cover_data["url_list"][0]
                
    except (KeyError, TypeError, IndexError) as e:
        pass  # Ignore extraction errors
    
    return result


class DouyinError(Exception):
    """Base exception for Douyin API errors"""
    pass


class NetworkError(DouyinError):
    """Network connection error"""
    pass


class DataExtractionError(DouyinError):
    """Data extraction error"""
    pass


class AuthenticationError(DouyinError):
    """Authentication error"""
    pass


class RateLimitError(DouyinError):
    """Rate limit exceeded error"""
    pass


class VerificationError(DouyinError):
    """Account verification required error"""
    pass