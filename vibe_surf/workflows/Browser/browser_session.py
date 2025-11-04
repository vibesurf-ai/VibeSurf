import asyncio
from typing import Any, List
from uuid import uuid4

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import MessageTextInput
from vibe_surf.langflow.io import BoolInput, IntInput, Output
from vibe_surf.browser.agent_browser_session import AgentBrowserSession


class BrowserSessionComponent(Component):
    display_name = "Browser Session"
    description = "Create browser sessions using the browser manager"
    icon = "monitor"

    inputs = [
        BoolInput(
            name="use_main_session",
            display_name="Use Main Session",
            info="Use the main browser session",
            value=False,
            advanced=True
        ),
        MessageTextInput(
            name="target_id",
            display_name="Target ID",
            info="Browser tab id",
            value='',
            advanced=True
        )
    ]

    outputs = [
        Output(
            display_name="Browser Session",
            name="browser_session",
            method="get_browser_session",
            types=["AgentBrowserSession"]
        )
    ]

    async def get_browser_session(self) -> AgentBrowserSession:
        """Get a specific session."""
        from vibe_surf.backend import shared_state
        browser_manager = shared_state.browser_manager

        if self.use_main_session:
            return browser_manager.main_browser_session
        else:
            target_id = None
            if self.target_id.strip():
                target_id = self.target_id.strip()
            browser_session = await browser_manager.register_agent(self._id, target_id=target_id)
            return browser_session
