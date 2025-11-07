import asyncio
from typing import Any, List
from uuid import uuid4

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import MessageTextInput, HandleInput
from vibe_surf.langflow.io import BoolInput, IntInput, Output
from vibe_surf.browser.agent_browser_session import AgentBrowserSession


class BrowserNavigateComponent(Component):
    display_name = "Navigation"
    description = "Navigates to a specific url"
    icon = "circle-arrow-out-up-right"

    inputs = [
        HandleInput(
            name="browser_session",
            display_name="Browser Session",
            info="Browser Session defined by VibeSurf",
            input_types=["AgentBrowserSession"],
            required=True
        ),
        MessageTextInput(
            name="url",
            display_name="URL",
            info="URL to navigate",
            required=True,
        )
    ]

    outputs = [
        Output(
            display_name="Browser Session",
            name="output_browser_session",
            method="browser_navigation",
            types=["AgentBrowserSession"]
        )
    ]

    async def browser_navigation(self) -> AgentBrowserSession:
        try:
            await self.browser_session.navigate_to_url(self.url)
            await asyncio.sleep(2)
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e
        finally:
            return self.browser_session
