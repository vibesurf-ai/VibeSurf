import asyncio
from typing import Any, List
from uuid import uuid4

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import MessageTextInput, HandleInput
from vibe_surf.langflow.io import BoolInput, IntInput, Output
from vibe_surf.langflow.schema.message import Message
from vibe_surf.browser.agent_browser_session import AgentBrowserSession


class BrowserGoBackComponent(Component):
    display_name = "Go Back"
    description = "Browser Go Forward"
    icon = "circle-arrow-left"

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
            display_name="Browser Session",
            name="output_browser_session",
            method="browser_go_back",
            types=["AgentBrowserSession"]
        )
    ]

    async def browser_go_back(self) -> AgentBrowserSession:
        try:
            page = await self.browser_session.get_current_page()
            await page.go_back()
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e
        finally:
            return self.browser_session
