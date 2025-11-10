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
from vibe_surf.langflow.field_typing import LanguageModel

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
            name="element_text",
            display_name="Element Text",
            info="Element Text you want to find and operate."
        ),
        MessageTextInput(
            name="element_hints",
            display_name="Element Hints",
            info="List of context hints like ['form', 'contact', 'personal info'] for finding this element. "
                 "Useful to distinguish when there are multiple elements with same text. ",
            list=True
        ),
        MessageTextInput(
            name="css_selector",
            display_name="CSS Selector",
            info="CSS Selector. Prioritize to use CSS Selector is you know it.",
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
            input_types=["LanguageModel"],
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
            await self.browser_session._wait_for_stable_network()

            element: Optional[Element] = None
            if self.element_text:
                from vibe_surf.browser.find_page_element import SemanticExtractor
                from vibe_surf.browser.page_operations import _try_direct_selector, _wait_for_element

                semantic_extractor = SemanticExtractor()
                element_mappings = await semantic_extractor.extract_semantic_mapping(self.browser_session)
                element_info = semantic_extractor.find_element_by_hierarchy(element_mappings,
                                                                            target_text=self.element_text,
                                                                            context_hints=self.element_hints)
                direct_selector = await _try_direct_selector(self.browser_session, self.element_text)
                selector_to_use = None
                if direct_selector:
                    selector_to_use = direct_selector
                elif element_info:
                    # Use hierarchical selector if it's more specific than the basic selector
                    hierarchical = element_info.get('hierarchical_selector', '')
                    basic = element_info.get('selectors', '')

                    # Prefer hierarchical if it has positional info (nth-of-type) or IDs
                    if hierarchical and ('#' in hierarchical or ':nth-of-type' in hierarchical):
                        selector_to_use = hierarchical
                    else:
                        selector_to_use = basic

                if selector_to_use:
                    page = await self.browser_session.get_current_page()

                    fallback_selectors = []
                    if element_info:
                        # Add hierarchical selector as first fallback
                        hierarchical_selector = element_info.get('hierarchical_selector')
                        if hierarchical_selector and hierarchical_selector != selector_to_use:
                            fallback_selectors.append(hierarchical_selector)

                        # Add original fallback selector
                        fallback_selector = element_info.get('fallback_selector')
                        if fallback_selector and fallback_selector not in fallback_selectors:
                            fallback_selectors.append(fallback_selector)

                        # Add XPath selector as final fallback
                        xpath_selector = element_info.get('text_xpath')
                        if xpath_selector:
                            fallback_selectors.append(f'xpath={xpath_selector}')

                    success, actual_selector = await _wait_for_element(self.browser_session, selector_to_use,
                                                                       fallback_selectors=fallback_selectors)
                    if not success:
                        raise ValueError("Failed to find selector")
                    else:
                        self.status = f"Get actual selector: {actual_selector}"
                        elements = await page.get_elements_by_css_selector(actual_selector)
                        if elements:
                            element = elements[0]

            elif self.css_selector:
                page = await self.browser_session.get_current_page()
                elements = await page.get_elements_by_css_selector(self.css_selector)
                self.log(f"Found {len(elements)} elements with CSS selector {self.css_selector}")
                self.log(elements)
                if elements:
                    element = elements[0]
            elif self.backend_node_id:
                page = await self.browser_session.get_current_page()
                element = await page.get_element(self.backend_node_id)
            elif self.element_prompt and self.llm:
                page = await self.browser_session.get_current_page()
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
