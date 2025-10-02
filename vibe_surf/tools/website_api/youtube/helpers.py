import pdb
import re
import json
import html
import random
import time
from typing import Dict, List, Tuple, Optional
from enum import Enum
from urllib.parse import parse_qs, unquote, urlparse


class SearchType(Enum):
    """Search type enumeration for YouTube"""
    VIDEO = "video"
    CHANNEL = "channel"
    PLAYLIST = "playlist"
    ALL = "all"


class SortType(Enum):
    """Sort type enumeration for YouTube search"""
    RELEVANCE = "relevance"
    DATE = "date"
    VIEW_COUNT = "viewCount"
    RATING = "rating"


class Duration(Enum):
    """Duration filter for YouTube search"""
    ANY = "any"
    SHORT = "short"  # < 4 minutes
    MEDIUM = "medium"  # 4-20 minutes
    LONG = "long"  # > 20 minutes


class UploadDate(Enum):
    """Upload date filter for YouTube search"""
    ANY = "any"
    HOUR = "hour"
    TODAY = "today"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


def generate_visitor_data() -> str:
    """Generate a random visitor data string for YouTube requests"""
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
    return ''.join(random.choices(chars, k=24))


def extract_cookies_from_browser(web_cookies: List[Dict]) -> Tuple[str, Dict[str, str]]:
    """Extract and format cookies from browser, filtering only YouTube related cookies"""
    cookie_dict = {}
    cookie_parts = []
    
    # YouTube domain patterns to filter
    youtube_domains = [
        '.youtube.com',
        # 'www.youtube.com',
        # 'm.youtube.com',
        # '.google.com'
    ]
    
    for cookie in web_cookies:
        if 'name' in cookie and 'value' in cookie and 'domain' in cookie:
            domain = cookie['domain']
            
            # Filter only YouTube related cookies
            if any(yt_domain in domain for yt_domain in youtube_domains):
                name = cookie['name']
                value = cookie['value']
                cookie_dict[name] = value
                cookie_parts.append(f"{name}={value}")
    
    cookie_string = "; ".join(cookie_parts)
    return cookie_string, cookie_dict


def extract_video_id_from_url(youtube_url: str) -> Optional[str]:
    """Extract video ID from YouTube URL"""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})',
        r'(?:watch\?v=)([0-9A-Za-z_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, youtube_url)
        if match:
            return match.group(1)
    
    return None


def extract_channel_id_from_url(channel_url: str) -> Optional[str]:
    """Extract channel ID from YouTube channel URL"""
    patterns = [
        r'(?:channel\/)([UC][0-9A-Za-z_-]{22})',
        r'(?:c\/)([^\/\?]+)',
        r'(?:user\/)([^\/\?]+)',
        r'(?:@)([^\/\?]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, channel_url)
        if match:
            return match.group(1)
    
    return None


def extract_playlist_id_from_url(playlist_url: str) -> Optional[str]:
    """Extract playlist ID from YouTube playlist URL"""
    match = re.search(r'(?:list=)([0-9A-Za-z_-]+)', playlist_url)
    if match:
        return match.group(1)
    return None


def parse_youtube_duration(duration_str: str) -> int:
    """Parse YouTube duration string (e.g., "PT4M13S") to seconds"""
    if not duration_str:
        return 0
    
    # Remove PT prefix
    duration_str = duration_str.replace('PT', '')
    
    # Extract hours, minutes, seconds
    hours = 0
    minutes = 0
    seconds = 0
    
    # Hours
    hour_match = re.search(r'(\d+)H', duration_str)
    if hour_match:
        hours = int(hour_match.group(1))
    
    # Minutes
    minute_match = re.search(r'(\d+)M', duration_str)
    if minute_match:
        minutes = int(minute_match.group(1))
    
    # Seconds
    second_match = re.search(r'(\d+)S', duration_str)
    if second_match:
        seconds = int(second_match.group(1))
    
    return hours * 3600 + minutes * 60 + seconds


def format_view_count(view_count: str) -> int:
    """Parse YouTube view count string to integer"""
    if not view_count:
        return 0
    
    try:
        # Remove non-numeric characters except for multipliers
        view_count = view_count.replace(',', '').replace(' ', '').lower()
        
        multipliers = {
            'k': 1000,
            'm': 1000000,
            'b': 1000000000,
            't': 1000000000000
        }
        
        for suffix, multiplier in multipliers.items():
            if view_count.endswith(suffix):
                number = float(view_count[:-1])
                return int(number * multiplier)
        
        # Try to parse as regular integer
        return int(''.join(filter(str.isdigit, view_count)))
    
    except (ValueError, TypeError):
        return 0


def parse_youtube_time(time_str: str) -> Optional[int]:
    """Parse YouTube time string to timestamp"""
    if not time_str:
        return None
    
    try:
        # Handle relative time like "2 hours ago", "1 day ago", etc.
        if "ago" in time_str.lower():
            time_str = time_str.lower().replace('ago', '').strip()
            
            if 'second' in time_str:
                seconds = int(re.search(r'(\d+)', time_str).group(1))
                return int(time.time()) - seconds
            elif 'minute' in time_str:
                minutes = int(re.search(r'(\d+)', time_str).group(1))
                return int(time.time()) - minutes * 60
            elif 'hour' in time_str:
                hours = int(re.search(r'(\d+)', time_str).group(1))
                return int(time.time()) - hours * 3600
            elif 'day' in time_str:
                days = int(re.search(r'(\d+)', time_str).group(1))
                return int(time.time()) - days * 86400
            elif 'week' in time_str:
                weeks = int(re.search(r'(\d+)', time_str).group(1))
                return int(time.time()) - weeks * 604800
            elif 'month' in time_str:
                months = int(re.search(r'(\d+)', time_str).group(1))
                return int(time.time()) - months * 2592000  # Approximate
            elif 'year' in time_str:
                years = int(re.search(r'(\d+)', time_str).group(1))
                return int(time.time()) - years * 31536000  # Approximate
        
        # Try to parse as timestamp
        return int(time_str)
    
    except (ValueError, AttributeError):
        return None


def process_youtube_text(text: str) -> str:
    """Process YouTube text content, remove HTML tags and clean up"""
    if not text:
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Decode HTML entities
    text = html.unescape(text)
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def validate_youtube_data(video_data: Dict) -> bool:
    """Validate if YouTube video data contains required fields"""
    required_fields = ["videoId", "title"]
    
    for field in required_fields:
        if field not in video_data:
            return False
    
    return True


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


def extract_ytcfg_data(html_content: str) -> Optional[Dict]:
    """Extract ytcfg data from YouTube page HTML"""
    try:
        # Try to find ytcfg.set pattern
        match = re.search(r'ytcfg\.set\s*\(\s*({.+?})\s*\)', html_content, re.DOTALL)
        if match:
            config_json = match.group(1)
            return json.loads(config_json)
    except (json.JSONDecodeError, IndexError):
        pass
    
    return None


def extract_initial_data(html_content: str) -> Optional[Dict]:
    """Extract initial data from YouTube page HTML"""
    try:
        # Try to find var ytInitialData pattern
        match = re.search(r'var ytInitialData = ({.+?});', html_content, re.DOTALL)
        if not match:
            # Try window.ytInitialData pattern
            match = re.search(r'window\["ytInitialData"\] = ({.+?});', html_content, re.DOTALL)
        
        if match:
            initial_data_json = match.group(1)
            return json.loads(initial_data_json)
    except (json.JSONDecodeError, IndexError):
        pass
    
    return None


def get_desktop_user_agent() -> str:
    """Get a random desktop user agent for YouTube requests"""
    ua_list = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ]
    return random.choice(ua_list)


def build_search_url(query: str, search_type: SearchType = SearchType.ALL, 
                    sort_by: SortType = SortType.RELEVANCE,
                    upload_date: UploadDate = UploadDate.ANY,
                    duration: Duration = Duration.ANY) -> str:
    """Build YouTube search URL with filters"""
    base_url = "https://www.youtube.com/results"
    params = {"search_query": query}
    
    # Add search type filter
    if search_type != SearchType.ALL:
        params["sp"] = _get_search_params(search_type, sort_by, upload_date, duration)
    
    param_string = "&".join([f"{k}={v}" for k, v in params.items()])
    return f"{base_url}?{param_string}"


def _get_search_params(search_type: SearchType, sort_by: SortType, 
                      upload_date: UploadDate, duration: Duration) -> str:
    """Generate search parameters string for YouTube search filters"""
    # This is a simplified version - YouTube's actual search parameters are more complex
    # and may need to be reverse-engineered for full functionality
    filters = []
    
    if search_type == SearchType.VIDEO:
        filters.append("EgIQAQ%253D%253D")
    elif search_type == SearchType.CHANNEL:
        filters.append("EgIQAg%253D%253D")
    elif search_type == SearchType.PLAYLIST:
        filters.append("EgIQAw%253D%253D")
    
    return "".join(filters)


# Exception classes
class YouTubeError(Exception):
    """Base exception for YouTube API errors"""
    pass


class NetworkError(YouTubeError):
    """Network connection error"""
    pass


class DataExtractionError(YouTubeError):
    """Data extraction error"""
    pass


class AuthenticationError(YouTubeError):
    """Authentication error"""
    pass


class RateLimitError(YouTubeError):
    """Rate limit exceeded error"""
    pass


class ContentNotFoundError(YouTubeError):
    """Content not found error"""
    pass


class ValidationError(YouTubeError):
    """Data validation error"""
    pass


def extract_continuation_token(data: Dict) -> Optional[str]:
    """Extract continuation token for pagination"""
    try:
        # Look for continuation token in various possible locations
        if isinstance(data, dict):
            # Check common continuation locations
            continuations = data.get("continuations", [])
            if continuations and isinstance(continuations, list):
                for continuation in continuations:
                    if isinstance(continuation, dict):
                        token = continuation.get("nextContinuationData", {}).get("continuation")
                        if token:
                            return token
            
            # Check other possible locations
            reload_continuation = data.get("reloadContinuationData", {}).get("continuation")
            if reload_continuation:
                return reload_continuation
    except Exception:
        pass
    
    return None


def decode_html_entities(text: str) -> str:
    """Decode HTML entities in text"""
    if not text:
        return ""
    
    # Decode HTML entities
    text = html.unescape(text)
    
    return text


def extract_thumbnail_url(thumbnails: List[Dict]) -> str:
    """Extract the best quality thumbnail URL from thumbnails list"""
    if not thumbnails:
        return ""
    
    # Sort by resolution and pick the highest quality
    sorted_thumbnails = sorted(thumbnails, key=lambda x: x.get('width', 0) * x.get('height', 0), reverse=True)
    
    if sorted_thumbnails:
        return sorted_thumbnails[0].get('url', '')
    
    return ""