import asyncio
from typing import Any, List
from uuid import uuid4
from browser_use.llm.base import BaseChatModel

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import MessageTextInput, HandleInput, DropdownInput
from vibe_surf.langflow.io import BoolInput, IntInput, Output
from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.langflow.schema.message import Message

class LLMProfilesComponent(Component):
    display_name = "LLM profiles"
    description = "Available llm profiles"
    icon = "brain"

    inputs = [
        DropdownInput(
            name="llm_profiles",
            display_name="LLM profiles",
            info="Available llm profiles",
            options=[],
            value='',
            input_types=["AgentBrowserSession"],
            required=True
        )
    ]

    outputs = [
        Output(
            display_name="LLM Model",
            name="llm_model",
            method="get_llm_profile_model",
            types=["BaseChatModel"]
        )
    ]

    async def get_llm_profile_model(self) -> BaseChatModel | None:
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