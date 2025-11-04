import asyncio
from typing import Any, List
from uuid import uuid4

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import MessageTextInput, HandleInput
from vibe_surf.langflow.io import BoolInput, IntInput, Output
from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.langflow.schema.message import Message

class CloseBrowserSessionComponent(Component):
    display_name = "Close Browser Session"
    description = "Close browser sessions"
    icon = "circle-x"

    inputs = [
        HandleInput(
            name="browser_session",
            display_name="Browser Session",
            info="Browser Session defined by VibeSurf",
            input_types=["AgentBrowserSession"],
            required=True
        )
    ]

    outputs = [
        Output(
            display_name="Result",
            name="result",
            method="close_browser_session",
            types=["Message"]
        )
    ]

    async def close_browser_session(self) -> Message | None:
        """Close a specific session."""
        if self.browser_session is None:
            raise RuntimeError("Browser session not found")
        if self.browser_session.main_browser_session is None:
            self.status = "Current Browser Session is main browser session. We can not close it."
            return Message(text=self.status)
        else:
            try:
                from vibe_surf.backend.shared_state import browser_manager
                await browser_manager.unregister_agent(self.browser_session.id, close_tabs=True)
                self.status = "Successfully closed browser session."
                return Message(text=self.status)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.status = "Failed to close browser session. {}".format(e)