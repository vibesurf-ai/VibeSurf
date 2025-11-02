import asyncio
from typing import Any, List
from uuid import uuid4

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import MessageTextInput, HandleInput
from vibe_surf.langflow.io import BoolInput, IntInput, Output
from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.langflow.schema.message import Message


class BrowserPressKeyComponent(Component):
    display_name = "Browser Press Key"
    description = "Press and send keys to browser"
    icon = "keyboard"

    inputs = [
        HandleInput(
            name="browser_session",
            display_name="Browser Session",
            info="Browser Session defined by VibeSurf",
            input_types=["AgentBrowserSession"],
            required=True
        ),
        MessageTextInput(
            name="keys",
            display_name="Keys",
            info="Keys to press and send to browser. Enter, Escape, Control+A and etc.",
            required=True,
        )
    ]

    outputs = [
        Output(
            display_name="Browser Session",
            name="browser_session",
            method="browser_press_keys",
            types=["AgentBrowserSession"]
        )
    ]

    async def browser_press_keys(self) -> AgentBrowserSession:
        try:
            page = await self.browser_session.get_current_page()
            await page.press(self.keys)
            return self.browser_session
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e
