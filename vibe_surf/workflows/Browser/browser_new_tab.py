import asyncio
from typing import Any, List
from uuid import uuid4

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import MessageTextInput, HandleInput
from vibe_surf.langflow.io import BoolInput, IntInput, Output
from vibe_surf.browser.agent_browser_session import AgentBrowserSession


class BrowserNewTabComponent(Component):
    display_name = "New Tab"
    description = "Create a new tab"
    icon = "circle-plus"

    inputs = [
        HandleInput(
            name="browser_session",
            display_name="Browser Session",
            info="Browser Session defined by VibeSurf",
            input_types=["AgentBrowserSession"],
            required=True
        ),
        MessageTextInput(
            name="new_tab_url",
            display_name="New Tab URL",
            info="New Tab URL",
        )
    ]

    outputs = [
        Output(
            display_name="Browser Session",
            name="output_browser_session",
            method="browser_new_tab",
            types=["AgentBrowserSession"]
        )
    ]

    async def browser_new_tab(self) -> AgentBrowserSession:
        try:
            new_url = self.new_tab_url or "chrome://newtab/"
            await self.browser_session.navigate_to_url(new_url, new_tab=True)
            self.status = f"Successfully created new tab ot {new_url}"
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e
        finally:
            return self.browser_session