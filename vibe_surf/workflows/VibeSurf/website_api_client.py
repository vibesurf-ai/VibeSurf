import asyncio
from typing import Any
from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import HandleInput, DropdownInput
from vibe_surf.langflow.io import Output
from vibe_surf.langflow.schema.dotdict import dotdict
from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.tools.website_api.base_client import BaseAPIClient
from vibe_surf.tools.website_api.douyin.client import DouyinApiClient
from vibe_surf.tools.website_api.weibo.client import WeiboApiClient
from vibe_surf.tools.website_api.xhs.client import XiaoHongShuApiClient
from vibe_surf.tools.website_api.youtube.client import YouTubeApiClient
from vibe_surf.tools.website_api.zhihu.client import ZhiHuClient


class WebsiteAPIClientComponent(Component):
    display_name = "Website API Client"
    description = "Initialize a website API client for Douyin, Weibo, XiaoHongShu, YouTube, or Zhihu"
    icon = "globe"

    inputs = [
        HandleInput(
            name="browser_session",
            display_name="Browser Session",
            info="Browser Session defined by VibeSurf",
            input_types=["AgentBrowserSession"],
            required=True
        ),
        DropdownInput(
            name="platform",
            display_name="Platform",
            info="Select the platform to initialize API client",
            options=["douyin", "weibo", "xiaohongshu", "youtube", "zhihu"],
            value="douyin",
            real_time_refresh=True
        )
    ]

    outputs = [
        Output(
            display_name="API Client",
            name="api_client",
            method="initialize_client",
            types=["BaseAPIClient"]
        )
    ]

    async def initialize_client(self) -> BaseAPIClient:
        """Initialize and setup the selected API client"""
        try:
            # Map platform names to client classes
            client_map = {
                "douyin": DouyinApiClient,
                "weibo": WeiboApiClient,
                "xiaohongshu": XiaoHongShuApiClient,
                "youtube": YouTubeApiClient,
                "zhihu": ZhiHuClient
            }

            # Get the client class
            client_class = client_map.get(self.platform)
            if not client_class:
                raise ValueError(f"Unknown platform: {self.platform}")

            # Initialize the client
            client = client_class(self.browser_session)

            # Setup the client (navigate to site and get cookies)
            await client.setup()

            self.status = f"✅ {self.platform.capitalize()} API client initialized successfully"
            return client

        except Exception as e:
            self.status = f"❌ Failed to initialize {self.platform} API client: {str(e)}"
            raise e