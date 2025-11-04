import asyncio
from typing import Any, List
from uuid import uuid4
from browser_use.llm.base import BaseChatModel

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import MessageTextInput, HandleInput, DropdownInput, StrInput
from vibe_surf.langflow.io import BoolInput, IntInput, Output
from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.langflow.schema.message import Message


class BrowserSelectOptionsComponent(Component):
    display_name = "Select Options"
    description = "Browser select options"
    icon = "square-check"

    inputs = [
        HandleInput(
            name="browser_session",
            display_name="Browser Session",
            info="Browser Session defined by VibeSurf",
            input_types=["AgentBrowserSession"],
            required=True
        ),
        StrInput(
            name="select_option",
            display_name="Select Option",
            info="Select Option",
            required=True,
            list=True
        ),
        MessageTextInput(
            name="css_selector",
            display_name="CSS Selector",
            info="CSS Selector defined by VibeSurf"
        ),
        IntInput(
            name="backend_node_id",
            display_name="Backend Node ID",
            info="Backend Node ID",
            advanced=True
        ),
        MessageTextInput(
            name="element_prompt",
            display_name="Element Prompt",
            info="Element Prompt",
            advanced=True
        ),
        HandleInput(
            name="llm",
            display_name="LLM Model",
            info="LLM Model defined by VibeSurf",
            input_types=["BaseChatModel"],
            advanced=True
        )
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
            element = None
            if self.css_selector:
                elements = await page.get_elements_by_css_selector(self.css_selector)
                self.log(f"Found {len(elements)} elements with CSS selector {self.css_selector}")
                self.log(elements)
                if elements:
                    element = elements[0]
            elif self.backend_node_id:
                element = await page.get_element(self.backend_node_id)
            elif self.element_prompt and self.llm:
                element = await page.get_element_by_prompt(self.element_prompt, self.llm)

            if not element:
                self.status = "No element found!"
                raise ValueError("No element found!")

            await element.select_option(self.select_option)
            self.status = f"Selected {self.select_option} on element {element}"
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e
        finally:
            return self.browser_session
