import asyncio
from typing import Any, List
from uuid import uuid4
from browser_use.llm.base import BaseChatModel
import os
from typing import Optional

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import MessageTextInput, HandleInput, DropdownInput
from vibe_surf.langflow.io import BoolInput, IntInput, Output
from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.langflow.schema.message import Message


class BrowserExtractContentComponent(Component):
    display_name = "Extract Content"
    description = "Browser extract content"
    icon = "text-search"

    inputs = [
        HandleInput(
            name="browser_session",
            display_name="Browser Session",
            info="Browser Session defined by VibeSurf",
            input_types=["AgentBrowserSession"],
            required=True
        ),
        MessageTextInput(
            name="extract_goal",
            display_name="Extract Goal",
            info="Goal for extraction.",
            required=True
        ),
        HandleInput(
            name="llm",
            display_name="LLM Model",
            info="LLM Model defined by VibeSurf",
            input_types=["BaseChatModel"],
            required=True
        )
    ]

    outputs = [
        Output(
            display_name="Browser Session",
            name="output_browser_session",
            method="browser_click_element",
            types=["AgentBrowserSession"],
            group_outputs=True
        ),
        Output(
            display_name="Extracted Content",
            name="extracted_content",
            method="browser_extract_content",
            types=["Message"],
            group_outputs=True,
        ),
    ]

    _extracted_content: Optional[str] = None

    async def browser_extract_content(self):
        try:
            page = await self.browser_session.get_current_page()
            await page.page.extract_content(
                self.extract_goal,
                ProductInfo,
                llm=self.llm,
            )
            return Message(text=self._extracted_content)
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e

    async def pass_browser_session(self) -> AgentBrowserSession:
        if not self._extracted_content:
            await self.browser_extract_content()
        return self.browser_session
