import asyncio
from typing import Any, List
from uuid import uuid4
from browser_use.llm.base import BaseChatModel

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import MessageTextInput, HandleInput, DropdownInput, StrInput
from vibe_surf.langflow.io import BoolInput, IntInput, Output
from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.langflow.schema.message import Message


class BrowserDragDropComponent(Component):
    display_name = "Drag and drop"
    description = "Browser drag and drop element"
    icon = "grip"

    inputs = [
        HandleInput(
            name="browser_session",
            display_name="Browser Session",
            info="Browser Session defined by VibeSurf",
            input_types=["AgentBrowserSession"],
            required=True
        ),
        MessageTextInput(
            name="src_css_selector",
            display_name="Source CSS Selector",
            info="Source CSS Selector"
        ),
        MessageTextInput(
            name="dst_css_selector",
            display_name="Destination CSS Selector",
            info="Destination CSS Selector"
        ),
    ]

    outputs = [
        Output(
            display_name="Browser Session",
            name="output_browser_session",
            method="browser_focus_element",
            types=["AgentBrowserSession"]
        )
    ]

    async def browser_focus_element(self) -> AgentBrowserSession:
        try:
            page = await self.browser_session.get_current_page()
            src_element = None
            if self.src_css_selector:
                src_elements = await page.get_elements_by_css_selector(self.src_css_selector)
                self.log(f"Found {len(src_elements)} elements with source CSS selector {self.src_css_selector}")
                self.log(src_elements)
                if src_elements:
                    src_element = src_elements[0]

            if not src_element:
                self.status = "No source element found!"
                raise ValueError(self.status)

            dst_element = None
            if self.dst_css_selector:
                dst_elements = await page.get_elements_by_css_selector(self.dst_css_selector)
                self.log(f"Found {len(dst_elements)} elements with source CSS selector {self.dst_css_selector}")
                self.log(dst_elements)
                if dst_elements:
                    dst_element = dst_elements[0]

            if not dst_element:
                self.status = "No destination element found!"
                raise ValueError(self.status)

            await src_element.drag_to(dst_element)
            self.status = f"Drag source element {src_element} to destination element {dst_element}"
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e
        finally:
            return self.browser_session
