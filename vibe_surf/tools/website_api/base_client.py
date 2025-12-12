"""Base API Client for Website API clients."""
from typing import Optional
from vibe_surf.browser.agent_browser_session import AgentBrowserSession


class BaseAPIClient:
    """
    Base class for all website API clients.
    Provides a common interface for client initialization and lifecycle management.
    """
    
    def __init__(self, browser_session: AgentBrowserSession, timeout: int = 60, proxy: Optional[str] = None):
        """
        Initialize the API client
        
        Args:
            browser_session: Browser session for authentication
            timeout: Request timeout in seconds
            proxy: Proxy URL if needed
        """
        self.browser_session = browser_session
        self.timeout = timeout
        self.proxy = proxy
    
    async def setup(self, target_id: Optional[str] = None):
        """
        Setup the API client by navigating to the site and extracting cookies
        
        Args:
            target_id: Specific browser target ID to use
        """
        raise NotImplementedError("Subclasses must implement setup()")
    
    async def close(self):
        """Close browser tab if created by this client"""
        raise NotImplementedError("Subclasses must implement close()")