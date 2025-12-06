"""
NewsNow API Client for fetching real-time and hottest news from various sources
"""
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
import httpx
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

from vibe_surf.logger import get_logger

from .helpers import (
    NewsItem, SourceResponse, SourceMetadata,
    NewsNowError, NetworkError, APIError,
    should_include_source, get_source_type
)

logger = get_logger(__name__)


class NewsNowClient:
    """
    NewsNow API client for fetching news from various sources
    """
    
    # Define source lists for different news types
    HOTTEST_SOURCES = [
        "baidu", "bilibili-hot-search", "chongbuluo-hot", "cls-hot", "coolapk",
        "douban", "douyin", "github-trending-today", "hackernews", "hupu",
        "ifeng", "juejin", "nowcoder", "producthunt", "sspai", "steam",
        "tencent-hot", "thepaper", "tieba", "toutiao", "wallstreetcn-hot",
        "weibo", "xueqiu-hotstock", "zhihu"
    ]
    
    REALTIME_SOURCES = [
        "cls-telegraph", "fastbull-express", "gelonghui", "ithome",
        "jin10", "pcbeta-windows11", "wallstreetcn-quick", "zaobao"
    ]
    
    def __init__(self, base_url: str = "https://newsnow.busiyi.world", timeout: int = 30):
        """
        Initialize the NewsNow API client
        
        Args:
            base_url: Base URL for the NewsNow API
            timeout: Request timeout in seconds (default: 30)
        """
        self.base_url = base_url
        self.timeout = timeout
        self.sources: Dict[str, SourceMetadata] = {}
        self._load_sources()
        
        # Default headers
        self.default_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        }
    
    def _load_sources(self):
        """Load sources configuration from JSON file"""
        sources_file = Path(__file__).parent / "sources.json"
        try:
            with open(sources_file, 'r', encoding='utf-8') as f:
                sources = json.load(f)
                for key in sources:
                    if key in self.HOTTEST_SOURCES + self.REALTIME_SOURCES:
                        self.sources[key] = sources[key]
            logger.info(f"Loaded {len(self.sources)} news sources")
        except Exception as e:
            logger.error(f"Failed to load sources configuration: {e}")
            raise NewsNowError(f"Failed to load sources: {e}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError))
    )
    async def _fetch_source_news(self, source_id: str) -> Optional[SourceResponse]:
        """
        Fetch news from a specific source with retry mechanism
        
        Args:
            source_id: The source ID to fetch news from
            
        Returns:
            Source response data or None if failed
        """
        url = f"{self.base_url}/api/s?id={source_id}"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self.default_headers)
                
                if response.status_code != 200:
                    logger.warning(f"Failed to fetch news for source {source_id}: HTTP {response.status_code}")
                    return None
                
                data = response.json()
                
                # Validate response structure
                if not isinstance(data, dict):
                    logger.warning(f"Invalid response format for source {source_id}")
                    return None
                
                if data.get("status") not in ["success", "cache"]:
                    logger.warning(f"API returned non-success status for source {source_id}: {data.get('status')}")
                    return None
                
                return data
                
        except httpx.TimeoutException:
            logger.warning(f"Timeout fetching news for source {source_id}")
            raise  # Let tenacity retry
        except (httpx.NetworkError, httpx.ConnectError) as e:
            logger.warning(f"Network error fetching news for source {source_id}: {e}")
            raise  # Let tenacity retry
        except Exception as e:
            logger.error(f"Unexpected error fetching news for source {source_id}: {e}")
            return None
    
    async def get_news(
        self,
        source_id: Optional[str] = None,
        count: int = 10,
        news_type: Optional[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch news from specified source(s)
        
        Args:
            source_id: Optional source ID. If None, fetches from all sources based on news_type
            count: Maximum number of news items to return per source (default: 10)
            news_type: Optional news type filter. Can be "realtime", "hottest", or None for both
            
        Returns:
            Dictionary with source IDs as keys and list of news items as values
            Each news item is a dict with: id, title, url, mobileUrl (optional), pubDate (optional), extra (optional)
        """
        results: Dict[str, List[Dict[str, Any]]] = {}
        
        # Determine which sources to fetch
        if source_id:
            # Single source fetch - use legacy method
            if source_id not in self.sources:
                logger.warning(f"Unknown source ID: {source_id}")
                return results
            
            source_metadata = self.sources[source_id]
            
            # Check if source should be included based on type filter
            if not should_include_source(source_metadata, news_type):
                logger.info(f"Source {source_id} skipped due to type filter: {news_type}")
                return results
            
            sources_to_fetch = {source_id: source_metadata}
            
            # Use legacy method for single source
            tasks = []
            source_ids = []
            
            for sid in sources_to_fetch.keys():
                tasks.append(self._fetch_source_news(sid))
                source_ids.append(sid)
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process responses
            for sid, response in zip(source_ids, responses):
                if isinstance(response, Exception):
                    logger.error(f"Exception fetching news for source {sid}: {response}")
                    continue
                
                if response is None:
                    continue
                
                # Extract and limit news items
                items = response.get("items", [])
                limited_items = items[:count] if count > 0 else items
                
                # Convert to simpler dict format
                news_list = []
                for item in limited_items:
                    news_dict = {
                        "id": item.get("id"),
                        "title": item.get("title"),
                        "url": item.get("url"),
                    }
                    
                    # Add optional fields if present
                    if "mobileUrl" in item:
                        news_dict["mobileUrl"] = item["mobileUrl"]
                    if "pubDate" in item:
                        news_dict["pubDate"] = item["pubDate"]
                    if "extra" in item:
                        news_dict["extra"] = item["extra"]
                    
                    news_list.append(news_dict)
                
                results[sid] = news_list
                logger.info(f"Fetched {len(news_list)} news items from source {sid}")
        else:
            # Batch fetch based on news type using predefined source lists
            if news_type == "hottest":
                source_ids = self.HOTTEST_SOURCES
            elif news_type == "realtime":
                source_ids = self.REALTIME_SOURCES
            else:
                # Fetch both
                source_ids = self.HOTTEST_SOURCES + self.REALTIME_SOURCES
            
            logger.info(f"Batch fetching news from {len(source_ids)} sources for type: {news_type}")
            
            # Use batch fetch API
            results = await self.fetch_news_batch(source_ids)
            
            # Limit items per source
            if count > 0:
                for sid in results:
                    results[sid] = results[sid][:count]
        
        return results
    
    def get_available_sources(
        self,
        news_type: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get list of available sources with their metadata
        
        Args:
            news_type: Optional filter by news type ("realtime", "hottest", or None for all)
            
        Returns:
            Dictionary of source metadata
        """
        filtered_sources = {}
        
        for source_id, metadata in self.sources.items():
            if should_include_source(metadata, news_type):
                # Create a clean metadata dict
                clean_metadata = {
                    "name": metadata.get("name", ""),
                    "home": metadata.get("home", ""),
                    "column": metadata.get("column", ""),
                    "color": metadata.get("color", ""),
                }
                
                # Add optional fields
                if "title" in metadata:
                    clean_metadata["title"] = metadata["title"]
                if "type" in metadata:
                    clean_metadata["type"] = metadata["type"]
                else:
                    clean_metadata["type"] = "all"
                if "desc" in metadata:
                    clean_metadata["desc"] = metadata["desc"]
                
                filtered_sources[source_id] = clean_metadata
        
        return filtered_sources
    
    def get_source_description(self) -> str:
        """
        Get a human-readable description of all available sources
        Similar to the JavaScript implementation
        
        Returns:
            String description of all sources
        """
        descriptions = []
        
        for source_id, metadata in self.sources.items():
            if metadata.get("redirect"):
                continue
            
            name = metadata.get("name", "")
            title = metadata.get("title", "")
            
            if title:
                descriptions.append(f"{name}-{title} id is {source_id}")
            else:
                descriptions.append(f"{name} id is {source_id}")
        
        return "; ".join(descriptions)
    
    async def fetch_news_batch(
        self,
        source_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Fetch news from multiple sources in batch using the /api/s/entire endpoint
        
        Args:
            source_ids: List of source IDs to fetch news from
            
        Returns:
            Dictionary with source IDs as keys and their news data
        """
        url = f"{self.base_url}/api/s/entire"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(f"POST request to {url} with {len(source_ids)} sources")
                # API expects {"sources": [...]} format, not just an array
                payload = {"sources": source_ids}
                response = await client.post(
                    url,
                    json=payload,
                    headers=self.default_headers
                )
                
                logger.info(f"Batch API response: status={response.status_code}, content-length={len(response.content)}")
                
                # Handle 204 No Content - treat as empty result (not an error)
                if response.status_code == 204:
                    logger.warning(f"Batch API returned 204 No Content - no news available")
                    return {}
                
                if response.status_code != 200:
                    logger.warning(f"Failed to fetch batch news: HTTP {response.status_code}")
                    return {}
                
                data = response.json()
                
                # Validate response is a list
                if not isinstance(data, list):
                    logger.warning(f"Invalid batch response format")
                    return {}
                
                # Convert list response to dict format
                results = {}
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    
                    source_id = item.get("id")
                    if not source_id:
                        continue
                    
                    items = item.get("items", [])
                    if items:
                        results[source_id] = items
                
                return results
                
        except httpx.TimeoutException:
            logger.warning(f"Timeout fetching batch news")
            return {}
        except Exception as e:
            logger.error(f"Error fetching batch news: {e}")
            return {}


# Convenience function for quick usage
async def fetch_news(
    source_id: Optional[str] = None,
    count: int = 10,
    news_type: Optional[str] = None,
    base_url: str = "https://newsnow.busiyi.world"
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Convenience function to fetch news without manually creating a client
    
    Args:
        source_id: Optional source ID. If None, fetches from all sources
        count: Maximum number of news items to return per source (default: 10)
        news_type: Optional news type filter ("realtime", "hottest", or None for both)
        base_url: Base URL for the NewsNow API
        
    Returns:
        Dictionary with source IDs as keys and list of news items as values
    """
    client = NewsNowClient(base_url=base_url)
    return await client.get_news(source_id=source_id, count=count, news_type=news_type)