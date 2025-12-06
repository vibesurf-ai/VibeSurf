"""
Helper functions and type definitions for NewsNow API
"""
from typing import TypedDict, List, Optional, Dict, Any
from enum import Enum


class NewsType(Enum):
    """News type enumeration"""
    REALTIME = "realtime"
    HOTTEST = "hottest"
    ALL = "all"


class NewsItemExtra(TypedDict, total=False):
    """Extra information for news item"""
    hover: Optional[str]
    date: Optional[int | str]
    info: Optional[bool | str]
    diff: Optional[int]
    icon: Optional[bool | str | Dict[str, Any]]


class NewsItem(TypedDict):
    """News item structure"""
    id: str | int
    title: str
    url: str
    mobileUrl: Optional[str]
    pubDate: Optional[int | str]
    extra: Optional[NewsItemExtra]


class SourceResponse(TypedDict):
    """API response structure for a single source"""
    status: str  # "success" or "cache"
    id: str
    updatedTime: int | str
    items: List[NewsItem]


class SourceMetadata(TypedDict, total=False):
    """Metadata for a news source"""
    redirect: Optional[str]
    name: str
    type: Optional[str]  # "realtime", "hottest", etc.
    title: Optional[str]
    column: str
    home: str
    color: str
    interval: int
    disable: Optional[str]
    desc: Optional[str]


class NewsNowError(Exception):
    """Base exception for NewsNow API errors"""
    pass


class NetworkError(NewsNowError):
    """Network connection error"""
    pass


class APIError(NewsNowError):
    """API response error"""
    pass


def get_source_type(source: SourceMetadata) -> str:
    """
    Get the type of a source (realtime, hottest, or both)
    
    Args:
        source: Source metadata
        
    Returns:
        Type string: "realtime", "hottest", or "all"
    """
    source_type = source.get("type", "")
    
    if source_type == "realtime":
        return NewsType.REALTIME.value
    elif source_type == "hottest":
        return NewsType.HOTTEST.value
    else:
        # If no specific type, consider it as general news (both)
        return NewsType.ALL.value


def should_include_source(source: SourceMetadata, news_type: Optional[str] = None) -> bool:
    """
    Check if a source should be included based on the requested news type
    
    Args:
        source: Source metadata
        news_type: Requested news type filter (realtime, hottest, or None for all)
        
    Returns:
        True if source should be included, False otherwise
    """
    # Skip sources with redirect
    if source.get("redirect"):
        return False
    
    # If no type filter, include all
    if news_type is None:
        return True
    
    source_type = get_source_type(source)
    
    # If source is "all" type, include it regardless of filter
    if source_type == NewsType.ALL.value:
        return True
    
    # Otherwise, must match the requested type
    return source_type == news_type