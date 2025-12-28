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

class BrowserMdContentComponent(Component):
    display_name = "Markdown Content"
    description = "Browser get markdown content"
    icon = "file-text"

    inputs = [
        HandleInput(
            name="browser_session",
            display_name="Browser Session",
            info="Browser Session defined by VibeSurf",
            input_types=["AgentBrowserSession"],
            required=True
        ),
        BoolInput(
            name="extract_links",
            display_name="Extract Links",
            info="Whether to extract links from the page",
            advanced=False,
            value=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Browser Session",
            name="output_browser_session",
            method="pass_browser_session",
            types=["AgentBrowserSession"],
            group_outputs=True,
        ),
        Output(
            display_name="Markdown Content",
            name="markdown_content",
            method="browser_get_markdown_content",
            types=["Message"],
            group_outputs=True,
        ),
    ]

    _md_content: Optional[str] = None

    async def browser_get_markdown_content(self):
        try:
            from browser_use.dom.markdown_extractor import extract_clean_markdown

            # Clear cache before extraction
            if self.browser_session._dom_watchdog:
                self.browser_session._dom_watchdog.clear_cache()
            self.browser_session._cached_browser_state_summary = None

            content, content_stats = await extract_clean_markdown(
                browser_session=self.browser_session, extract_links=self.extract_links
            )

            self._md_content = content
            self.status = f"Extracted markdown content ({len(content)} chars, {content_stats.get('total_elements', 0)} elements)"
            return Message(text=content)
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e

    async def pass_browser_session(self) -> AgentBrowserSession:
        if not self._md_content:
            await self.browser_get_markdown_content()
        return self.browser_session
