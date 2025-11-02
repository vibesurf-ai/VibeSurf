import asyncio
import os
from typing import Any, List
from uuid import uuid4
from typing import Optional

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import MessageTextInput, HandleInput
from vibe_surf.langflow.io import BoolInput, IntInput, Output
from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.langflow.schema.message import Message

class BrowserWaitComponent(Component):
    display_name = "Wait"
    description = "Wait seconds for stable browser page."
    icon = "clock"

    inputs = [
        HandleInput(
            name="browser_session",
            display_name="Browser Session",
            info="Browser Session defined by VibeSurf",
            input_types=["AgentBrowserSession"],
            required=True
        ),
        IntInput(
            name="seconds",
            display_name="Seconds",
            info="Seconds to wait for stable browser page",
            value=1
        )
    ]

    outputs = [
        Output(
            display_name="Browser Session",
            name="output_browser_session",
            method="pass_browser_session",
            types=["AgentBrowserSession"],
            group_outputs=True,
        ),
    ]

    async def pass_browser_session(self) -> AgentBrowserSession:
        await asyncio.sleep(self.seconds)
        return self.browser_session
