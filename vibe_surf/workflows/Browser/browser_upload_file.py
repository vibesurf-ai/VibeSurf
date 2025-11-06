import asyncio
from typing import Any, List
from uuid import uuid4
from browser_use.llm.base import BaseChatModel
from typing import Optional
from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import MessageTextInput, HandleInput, DropdownInput, FileInput
from vibe_surf.langflow.io import BoolInput, IntInput, Output
from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.langflow.schema.message import Message
from browser_use.actor.element import Element, ElementInfo

class BrowserUploadFileComponent(Component):
    display_name = "Upload File"
    description = "Browser upload file"
    icon = "upload"

    inputs = [
        HandleInput(
            name="browser_session",
            display_name="Browser Session",
            info="Browser Session defined by VibeSurf",
            input_types=["AgentBrowserSession"],
            required=True
        ),
        FileInput(
            name="file",
            display_name="File",
            info="File to upload",
            required=True,
            fileTypes=['json', 'md', 'csv', 'pdf', 'png', 'jpg', 'jpeg', 'txt', 'py', 'js'],
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
        ),
    ]

    outputs = [
        Output(
            display_name="Browser Session",
            name="output_browser_session",
            method="browser_upload_file",
            types=["AgentBrowserSession"]
        )
    ]

    async def browser_upload_file(self) -> AgentBrowserSession:
        try:
            page = await self.browser_session.get_current_page()
            element: Optional[Element] = None
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

            element_info: ElementInfo = await element.get_basic_info()
            if element_info["nodeName"] != 'INPUT' and element_info["attributes"].get('type', '').lower() != 'file':
                raise ValueError(f"{element} does not support file upload!")

            # Get CDP client and session
            cdp_client = self.browser_session.cdp_client
            # Set file(s) to upload
            await cdp_client.send.DOM.setFileInputFiles(
                params={
                    'files': [self.file],
                    'backendNodeId': element._backend_node_id,
                },
                session_id=element._session_id,
            )
            self.status = f"Upload file: {self.file} on element {element}"
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e
        finally:
            return self.browser_session
