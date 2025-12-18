import asyncio
from typing import Any, List, Optional, Dict, Tuple
from uuid import uuid4

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import MessageTextInput, HandleInput
from vibe_surf.langflow.io import BoolInput, IntInput, Output
from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.langflow.schema.data import Data

class BrowserPageInfoComponent(Component):
    display_name = "Page Information"
    description = "Information of current page"
    icon = "book-open-check"

    inputs = [
        HandleInput(
            name="browser_session",
            display_name="Browser Session",
            info="Browser Session defined by VibeSurf",
            input_types=["AgentBrowserSession"],
            required=True
        ),
    ]

    outputs = [
        Output(
            display_name="Page Info",
            name="page_info",
            method="get_page_information",
            types=["Data"],
            group_outputs=True,
        ),
    ]

    _page_info: Optional[Dict[str, Any]] = None

    async def get_page_information(self) -> Data:
        try:
            await self.browser_session._wait_for_stable_network(max_attempt=3)
            page = await self.browser_session.get_current_page()
            url = await page.get_url()
            title = await page.get_title()
            cdp_client = self.browser_session.agent_focus.cdp_client
            session_id = self.browser_session.agent_focus.session_id

            # Get viewport dimensions
            layout_metrics = await cdp_client.send.Page.getLayoutMetrics(session_id=session_id)
            viewport_width = layout_metrics['layoutViewport']['clientWidth']
            viewport_height = layout_metrics['layoutViewport']['clientHeight']
            page_info = {
                "url": url,
                "title": title,
                "viewport_width": viewport_width,
                "viewport_height": viewport_height,
            }
            self._page_info = page_info
            return Data(data=self._page_info)
        except Exception as e:
            self._page_info = None
            import traceback
            traceback.print_exc()
            raise e
