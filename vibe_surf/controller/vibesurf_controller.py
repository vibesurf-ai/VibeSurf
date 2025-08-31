import pdb
import os
import asyncio
import json
import enum
import base64
import mimetypes

from typing import Optional, Type, Callable, Dict, Any, Union, Awaitable, TypeVar
from pydantic import BaseModel
from browser_use.controller.service import Controller
import logging
from browser_use.agent.views import ActionModel, ActionResult
from browser_use.utils import time_execution_sync
from browser_use.filesystem.file_system import FileSystem
from browser_use.browser import BrowserSession
from browser_use.browser.events import UploadFileEvent
from browser_use.observability import observe_debug
from browser_use.controller.views import (
    ClickElementAction,
    CloseTabAction,
    DoneAction,
    GetDropdownOptionsAction,
    GoToUrlAction,
    InputTextAction,
    NoParamsAction,
    ScrollAction,
    SearchGoogleAction,
    SelectDropdownOptionAction,
    SendKeysAction,
    StructuredOutputAction,
    SwitchTabAction,
    UploadFileAction,
)
from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import UserMessage, ContentPartTextParam, ContentPartImageParam, ImageURL
from browser_use.dom.service import EnhancedDOMTreeNode
from browser_use.browser.views import BrowserError
from browser_use.mcp.client import MCPClient


from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.controller.views import HoverAction, ExtractionAction, FileExtractionAction
from vibe_surf.controller.mcp_client import VibeSurfMCPClient

logger = logging.getLogger(__name__)

Context = TypeVar('Context')

T = TypeVar('T', bound=BaseModel)


class VibeSurfController(Controller):
    def __init__(self,
                 exclude_actions: list[str] = [],
                 output_model: type[T] | None = None,
                 display_files_in_done_text: bool = True,
                 mcp_server_config: Optional[Dict[str, Any]] = None
                 ):
        super().__init__(exclude_actions=exclude_actions, output_model=output_model,
                         display_files_in_done_text=display_files_in_done_text)
        self._register_browser_actions()
        self.mcp_server_config = mcp_server_config
        self.mcp_clients = {}

    def _register_browser_actions(self):
        """Register custom browser actions"""

        @self.registry.action(
            'Hover over an element',
            param_model=HoverAction,
        )
        async def hover_element(params: HoverAction, browser_session: AgentBrowserSession):
            """Hovers over the element specified by its index from the cached selector map or by XPath."""
            try:
                if params.xpath:
                    # Find element by XPath using CDP
                    cdp_session = await browser_session.get_or_create_cdp_session()
                    result = await cdp_session.cdp_client.send.Runtime.evaluate(
                        params={
                            'expression': f"""
        						(() => {{
        							const element = document.evaluate('{params.xpath}', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
        							if (element) {{
        								const rect = element.getBoundingClientRect();
        								return {{found: true, x: rect.x + rect.width/2, y: rect.y + rect.height/2}};
        							}}
        							return {{found: false}};
        						}})()
        					""",
                            'returnByValue': True,
                        },
                        session_id=cdp_session.session_id,
                    )
                    element_info = result.get('result', {}).get('value', {})
                    if not element_info.get('found'):
                        raise Exception(f'Failed to locate element with XPath {params.xpath}')
                    x, y = element_info['x'], element_info['y']

                elif params.selector:
                    # Find element by CSS selector using CDP
                    cdp_session = await browser_session.get_or_create_cdp_session()
                    result = await cdp_session.cdp_client.send.Runtime.evaluate(
                        params={
                            'expression': f"""
        						(() => {{
        							const element = document.querySelector('{params.selector}');
        							if (element) {{
        								const rect = element.getBoundingClientRect();
        								return {{found: true, x: rect.x + rect.width/2, y: rect.y + rect.height/2}};
        							}}
        							return {{found: false}};
        						}})()
        					""",
                            'returnByValue': True,
                        },
                        session_id=cdp_session.session_id,
                    )
                    element_info = result.get('result', {}).get('value', {})
                    if not element_info.get('found'):
                        raise Exception(f'Failed to locate element with CSS Selector {params.selector}')
                    x, y = element_info['x'], element_info['y']

                elif params.index is not None:
                    # Use index to locate the element
                    selector_map = await browser_session.get_selector_map()
                    if params.index not in selector_map:
                        raise Exception(
                            f'Element index {params.index} does not exist - retry or use alternative actions')
                    element_node = selector_map[params.index]

                    # Get element position
                    if not element_node.absolute_position:
                        raise Exception(f'Element at index {params.index} has no position information')

                    x = element_node.absolute_position.x + element_node.absolute_position.width / 2
                    y = element_node.absolute_position.y + element_node.absolute_position.height / 2

                else:
                    raise Exception('Either index, xpath, or selector must be provided')

                # Perform hover using CDP mouse events
                cdp_session = await browser_session.get_or_create_cdp_session()

                # Move mouse to the element position
                await cdp_session.cdp_client.send.Input.dispatchMouseEvent(
                    params={
                        'type': 'mouseMoved',
                        'x': x,
                        'y': y,
                    },
                    session_id=cdp_session.session_id,
                )

                # Wait a bit for hover state to trigger
                await asyncio.sleep(0.1)

                msg = (
                    f'🖱️ Hovered over element at index {params.index}'
                    if params.index is not None
                    else f'🖱️ Hovered over element with XPath {params.xpath}'
                    if params.xpath
                    else f'🖱️ Hovered over element with selector {params.selector}'
                )
                return ActionResult(extracted_content=msg, include_in_memory=True)

            except Exception as e:
                error_msg = f'❌ Failed to hover over element: {str(e)}'
                return ActionResult(error=error_msg)

        # =======================
        # NAVIGATION ACTIONS
        # =======================

        @self.registry.action(
            'Search the query in Google, the query should be a search query like humans search in Google, concrete and not vague or super long.',
            param_model=SearchGoogleAction,
        )
        async def search_google(params: SearchGoogleAction, browser_session: AgentBrowserSession):
            search_url = f'https://www.google.com/search?q={params.query}&udm=14'

            try:
                # Use AgentBrowserSession's direct navigation method
                await browser_session.navigate_to_url(search_url, new_tab=False)
                memory = f"Searched Google for '{params.query}'"
                msg = f'🔍 {memory}'
                logger.info(msg)
                return ActionResult(extracted_content=memory, include_in_memory=True, long_term_memory=memory)
            except Exception as e:
                logger.error(f'Failed to search Google: {e}')
                return ActionResult(error=f'Failed to search Google for "{params.query}": {str(e)}')

        @self.registry.action(
            'Navigate to URL, set new_tab=True to open in new tab, False to navigate in current tab',
            param_model=GoToUrlAction
        )
        async def go_to_url(params: GoToUrlAction, browser_session: AgentBrowserSession):
            try:
                # Use AgentBrowserSession's direct navigation method
                await browser_session.navigate_to_url(params.url, new_tab=params.new_tab)

                if params.new_tab:
                    memory = f'Opened new tab with URL {params.url}'
                    msg = f'🔗 Opened new tab with url {params.url}'
                else:
                    memory = f'Navigated to {params.url}'
                    msg = f'🔗 {memory}'

                logger.info(msg)
                return ActionResult(extracted_content=msg, include_in_memory=True, long_term_memory=memory)
            except Exception as e:
                logger.error(f'❌ Navigation failed: {str(e)}')
                return ActionResult(error=f'Navigation failed: {str(e)}')

        @self.registry.action(
            'Go back',
        )
        async def go_back(browser_session: AgentBrowserSession):
            try:
                cdp_session = await browser_session.get_or_create_cdp_session()
                history = await cdp_session.cdp_client.send.Page.getNavigationHistory(session_id=cdp_session.session_id)
                current_index = history['currentIndex']
                entries = history['entries']

                # Check if we can go back
                if current_index <= 0:
                    memory = msg = '⚠️ Cannot go back - no previous entry in history'
                    logger.info(msg)
                    return ActionResult(extracted_content=memory)

                # Navigate to the previous entry
                previous_entry_id = entries[current_index - 1]['id']
                await cdp_session.cdp_client.send.Page.navigateToHistoryEntry(
                    params={'entryId': previous_entry_id}, session_id=cdp_session.session_id
                )

                # Wait for navigation
                await asyncio.sleep(0.5)
                memory = 'Navigated back'
                msg = f'🔙 {memory}'
                logger.info(msg)
                return ActionResult(extracted_content=memory)
            except Exception as e:
                logger.error(f'Failed to go back: {str(e)}')
                return ActionResult(error=f'Failed to go back: {str(e)}')

        @self.registry.action(
            'Switch tab',
            param_model=SwitchTabAction
        )
        async def switch_tab(params: SwitchTabAction, browser_session: AgentBrowserSession):
            try:

                if params.tab_id:
                    target_id = await browser_session.get_target_id_from_tab_id(params.tab_id)
                elif params.url:
                    target_id = await browser_session.get_target_id_from_url(params.url)
                else:
                    target_id = await browser_session.get_most_recently_opened_target_id()

                # Switch to target using CDP
                await browser_session.get_or_create_cdp_session(target_id, focus=True)

                memory = f'Switched to Tab with ID {target_id[-4:]}'
                logger.info(f'🔄 {memory}')
                return ActionResult(extracted_content=memory, include_in_memory=True, long_term_memory=memory)
            except Exception as e:
                logger.error(f'Failed to switch tab: {str(e)}')
                return ActionResult(error=f'Failed to switch to tab {params.tab_id or params.url}: {str(e)}')

        @self.registry.action(
            """Extract structured, semantic data (e.g. product description, price, all information about XYZ) from the current webpage based on a textual query.
        This tool takes the entire markdown of the page and extracts the query from it.
        Set extract_links=True ONLY if your query requires extracting links/URLs from the page.
        Only use this for specific queries for information retrieval from the page. Don't use this to get interactive elements - the tool does not see HTML elements, only the markdown.
        Note: Extracting from the same page will yield the same results unless more content is loaded (e.g., through scrolling for dynamic content, or new page is loaded) - so one extraction per page state is sufficient. If you want to scrape a listing of many elements always first scroll a lot until the page end to load everything and then call this tool in the end.
        If you called extract_structured_data in the last step and the result was not good (e.g. because of antispam protection), use the current browser state and scrolling to get the information, dont call extract_structured_data again.
        """,
            param_model=ExtractionAction
        )
        async def extract_structured_data(
                params: ExtractionAction,
                browser_session: AgentBrowserSession,
                page_extraction_llm: BaseChatModel,
                file_system: FileSystem,
        ):
            try:
                # Use AgentBrowserSession's direct method to get HTML content
                target_id = None
                if params.tab_id:
                    target_id = await browser_session.get_target_id_from_tab_id(params.tab_id)
                page_html = await browser_session.get_html_content(target_id)

                # Simple markdown conversion
                import re
                import markdownify

                if params.extract_links:
                    content = markdownify.markdownify(page_html, heading_style='ATX', bullets='-')
                else:
                    content = markdownify.markdownify(page_html, heading_style='ATX', bullets='-', strip=['a'])
                    # Remove all markdown links and images, keep only the text
                    content = re.sub(r'!\[.*?\]\([^)]*\)', '', content, flags=re.MULTILINE | re.DOTALL)  # Remove images
                    content = re.sub(
                        r'\[([^\]]*)\]\([^)]*\)', r'\1', content, flags=re.MULTILINE | re.DOTALL
                    )  # Convert [text](url) -> text

                # Remove weird positioning artifacts
                content = re.sub(r'❓\s*\[\d+\]\s*\w+.*?Position:.*?Size:.*?\n?', '', content,
                                 flags=re.MULTILINE | re.DOTALL)
                content = re.sub(r'Primary: UNKNOWN\n\nNo specific evidence found', '', content,
                                 flags=re.MULTILINE | re.DOTALL)
                content = re.sub(r'UNKNOWN CONFIDENCE', '', content, flags=re.MULTILINE | re.DOTALL)
                content = re.sub(r'!\[\]\(\)', '', content, flags=re.MULTILINE | re.DOTALL)

                # Simple truncation to 30k characters
                if len(content) > 30000:
                    content = content[:30000] + '\n\n... [Content truncated at 30k characters] ...'

                # Simple prompt
                prompt = f"""Extract the requested information from this webpage content.
                
Query: {params.query}

Webpage Content:
{content}

Provide the extracted information in a clear, structured format."""

                from browser_use.llm.messages import UserMessage

                response = await asyncio.wait_for(
                    page_extraction_llm.ainvoke([UserMessage(content=prompt)]),
                    timeout=120.0,
                )

                extracted_content = f'Query: {params.query}\nExtracted Content:\n{response.completion}'

                # Simple memory handling
                if len(extracted_content) < 1000:
                    memory = extracted_content
                    include_extracted_content_only_once = False
                else:
                    save_result = await file_system.save_extracted_content(extracted_content)
                    current_url = await browser_session.get_current_page_url()
                    memory = (
                        f'Extracted content from {current_url} for query: {params.query}\nContent saved to file system: {save_result}'
                    )
                    include_extracted_content_only_once = True

                logger.info(f'📄 {memory}')
                return ActionResult(
                    extracted_content=extracted_content,
                    include_extracted_content_only_once=include_extracted_content_only_once,
                    long_term_memory=memory,
                )
            except Exception as e:
                logger.debug(f'Error extracting content: {e}')
                raise RuntimeError(str(e))

        @self.registry.action('Read file_name from file system. If this is a file not in Current workspace dir or with a absolute path, Set external_file=True.')
        async def read_file(file_name: str, external_file: bool, file_system: FileSystem):
            result = await file_system.read_file(file_name, external_file=external_file)

            MAX_MEMORY_SIZE = 1000
            if len(result) > MAX_MEMORY_SIZE:
                lines = result.splitlines()
                display = ''
                lines_count = 0
                for line in lines:
                    if len(display) + len(line) < MAX_MEMORY_SIZE:
                        display += line + '\n'
                        lines_count += 1
                    else:
                        break
                remaining_lines = len(lines) - lines_count
                memory = f'{display}{remaining_lines} more lines...' if remaining_lines > 0 else display
            else:
                memory = result
            logger.info(f'💾 {memory}')
            return ActionResult(
                extracted_content=result,
                include_in_memory=True,
                long_term_memory=memory,
                include_extracted_content_only_once=True,
            )

        @self.registry.action(
            'Extract content from a file. Support image files, pdf and more.',
            param_model=FileExtractionAction,
        )
        async def extract_content_from_file(
                params: FileExtractionAction,
                page_extraction_llm: BaseChatModel,
                file_system: FileSystem,
        ):
            try:
                # Get file path
                file_path = params.file_path
                
                # Check if file exists
                if not os.path.exists(file_path):
                    raise Exception(f'File not found: {file_path}')
                
                # Determine if file is an image based on MIME type
                mime_type, _ = mimetypes.guess_type(file_path)
                is_image = mime_type and mime_type.startswith('image/')
                
                if is_image:
                    # Handle image files with LLM vision
                    try:
                        # Read image file and encode to base64
                        with open(file_path, 'rb') as image_file:
                            image_data = image_file.read()
                            image_base64 = base64.b64encode(image_data).decode('utf-8')
                        
                        # Create content parts similar to the user's example
                        content_parts: list[ContentPartTextParam | ContentPartImageParam] = [
                            ContentPartTextParam(text=f"Query: {params.query}")
                        ]
                        
                        # Add the image
                        content_parts.append(
                            ContentPartImageParam(
                                image_url=ImageURL(
                                    url=f'data:{mime_type};base64,{image_base64}',
                                    media_type=mime_type,
                                    detail='high',
                                ),
                            )
                        )
                        
                        # Create user message and invoke LLM
                        user_message = UserMessage(content=content_parts, cache=True)
                        response = await asyncio.wait_for(
                            page_extraction_llm.ainvoke([user_message]),
                            timeout=120.0,
                        )
                        
                        extracted_content = f'File: {file_path}\nQuery: {params.query}\nExtracted Content:\n{response.completion}'
                        
                    except Exception as e:
                        raise Exception(f'Failed to process image file {file_path}: {str(e)}')
                        
                else:
                    # Handle non-image files by reading content
                    try:
                        file_content = await file_system.read_file(file_path, external_file=True)
                        
                        # Create a simple prompt for text extraction
                        prompt = f"""Extract the requested information from this file content.

Query: {params.query}

File: {file_path}
File Content:
{file_content}

Provide the extracted information in a clear, structured format."""

                        response = await asyncio.wait_for(
                            page_extraction_llm.ainvoke([UserMessage(content=prompt)]),
                            timeout=120.0,
                        )
                        
                        extracted_content = f'File: {file_path}\nQuery: {params.query}\nExtracted Content:\n{response.completion}'
                        
                    except Exception as e:
                        raise Exception(f'Failed to read file {file_path}: {str(e)}')
                
                # Handle memory storage
                if len(extracted_content) < 1000:
                    memory = extracted_content
                    include_extracted_content_only_once = False
                else:
                    save_result = await file_system.save_extracted_content(extracted_content)
                    memory = (
                        f'Extracted content from file {file_path} for query: {params.query}\nContent saved to file system: {save_result}'
                    )
                    include_extracted_content_only_once = True

                logger.info(f'📄 Extracted content from file: {file_path}')
                return ActionResult(
                    extracted_content=extracted_content,
                    include_extracted_content_only_once=include_extracted_content_only_once,
                    long_term_memory=memory,
                )
                
            except Exception as e:
                logger.debug(f'Error extracting content from file: {e}')
                raise RuntimeError(str(e))

    async def register_mcp_clients(self, mcp_server_config: Optional[Dict[str, Any]] = None):
        self.mcp_server_config = mcp_server_config or self.mcp_server_config
        if self.mcp_server_config:
            await self.unregister_mcp_clients()
            await self.register_mcp_tools()

    async def register_mcp_tools(self):
        """
        Register the MCP tools used by this controller.
        """
        if not self.mcp_server_config:
            return
            
        # Handle both formats: with or without "mcpServers" key
        mcp_servers = self.mcp_server_config.get('mcpServers', self.mcp_server_config)
        
        if not mcp_servers:
            return
            
        for server_name, server_config in mcp_servers.items():
            try:
                logger.info(f'Connecting to MCP server: {server_name}')
                
                # Create MCP client
                client = VibeSurfMCPClient(
                    server_name=server_name,
                    command=server_config['command'],
                    args=server_config['args'],
                    env=server_config.get('env', None)
                )
                
                # Connect to the MCP server
                await client.connect(timeout=200)
                
                # Register tools to controller with prefix
                prefix = f"mcp.{server_name}."
                await client.register_to_controller(
                    controller=self,
                    prefix=prefix
                )
                
                # Store client for later cleanup
                self.mcp_clients[server_name] = client
                
                logger.info(f'Successfully registered MCP server: {server_name} with prefix: {prefix}')
                
            except Exception as e:
                logger.error(f'Failed to register MCP server {server_name}: {str(e)}')
                # Continue with other servers even if one fails

    async def unregister_mcp_clients(self):
        """
        Unregister and disconnect all MCP clients.
        """
        # Disconnect all MCP clients
        for server_name, client in self.mcp_clients.items():
            try:
                logger.info(f'Disconnecting MCP server: {server_name}')
                await client.disconnect()
            except Exception as e:
                logger.error(f'Failed to disconnect MCP server {server_name}: {str(e)}')
        
        # Remove MCP tools from registry
        try:
            # Get all registered actions
            actions_to_remove = []
            for action_name in list(self.registry.registry.actions.keys()):
                if action_name.startswith('mcp.'):
                    actions_to_remove.append(action_name)
            
            # Remove MCP actions from registry
            for action_name in actions_to_remove:
                if action_name in self.registry.registry.actions:
                    del self.registry.registry.actions[action_name]
                    logger.info(f'Removed MCP action: {action_name}')
                    
        except Exception as e:
            logger.error(f'Failed to remove MCP actions from registry: {str(e)}')
        
        # Clear the clients dictionary
        self.mcp_clients.clear()
        logger.info('All MCP clients unregistered and disconnected')

    @observe_debug(ignore_input=True, ignore_output=True, name='act')
    @time_execution_sync('--act')
    async def act(
            self,
            action: ActionModel,
            browser_session: BrowserSession| None = None,
            #
            page_extraction_llm: BaseChatModel | None = None,
            sensitive_data: dict[str, str | dict[str, str]] | None = None,
            available_file_paths: list[str] | None = None,
            file_system: FileSystem | None = None,
            #
            context: Context | None = None,
    ) -> ActionResult:
        """Execute an action"""

        for action_name, params in action.model_dump(exclude_unset=True).items():
            if params is not None:
                try:
                    result = await self.registry.execute_action(
                        action_name=action_name,
                        params=params,
                        browser_session=browser_session,
                        page_extraction_llm=page_extraction_llm,
                        file_system=file_system,
                        sensitive_data=sensitive_data,
                        available_file_paths=available_file_paths,
                        context=context,
                    )
                except Exception as e:
                    result = ActionResult(error=str(e))

                if isinstance(result, str):
                    return ActionResult(extracted_content=result)
                elif isinstance(result, ActionResult):
                    return result
                elif result is None:
                    return ActionResult()
                else:
                    raise ValueError(f'Invalid action result type: {type(result)} of {result}')
        return ActionResult()