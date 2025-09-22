import pdb
import os
import asyncio
import json
import enum
import base64
import mimetypes
import datetime
from pathvalidate import sanitize_filename
from typing import Optional, Type, Callable, Dict, Any, Union, Awaitable, TypeVar
from pydantic import BaseModel
from browser_use.tools.service import Tools
import logging
from browser_use.agent.views import ActionModel, ActionResult
from browser_use.utils import time_execution_sync
from browser_use.filesystem.file_system import FileSystem
from browser_use.browser import BrowserSession
from browser_use.browser.events import UploadFileEvent
from browser_use.observability import observe_debug
from browser_use.tools.views import (
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
from vibe_surf.tools.views import HoverAction, ExtractionAction, FileExtractionAction
from vibe_surf.tools.mcp_client import CustomMCPClient
from vibe_surf.tools.file_system import CustomFileSystem
from vibe_surf.logger import get_logger
from vibe_surf.tools.vibesurf_tools import VibeSurfTools

logger = get_logger(__name__)

Context = TypeVar('Context')

T = TypeVar('T', bound=BaseModel)


class BrowserUseTools(Tools, VibeSurfTools):
    def __init__(self,
                 exclude_actions: list[str] = [],
                 output_model: type[T] | None = None,
                 display_files_in_done_text: bool = True,
                 ):
        Tools.__init__(self, exclude_actions=exclude_actions, output_model=output_model,
                       display_files_in_done_text=display_files_in_done_text)
        self._register_browser_actions()
        self._register_file_actions()

    def _register_done_action(self, output_model: type[T] | None, display_files_in_done_text: bool = True):
        if output_model is not None:
            self.display_files_in_done_text = display_files_in_done_text

            @self.registry.action(
                'Complete task - with return text and if the task is finished (success=True) or not yet completely finished (success=False), because last step is reached',
                param_model=StructuredOutputAction[output_model],
            )
            async def done(params: StructuredOutputAction):
                # Exclude success from the output JSON since it's an internal parameter
                output_dict = params.data.model_dump()

                # Enums are not serializable, convert to string
                for key, value in output_dict.items():
                    if isinstance(value, enum.Enum):
                        output_dict[key] = value.value

                return ActionResult(
                    is_done=True,
                    success=params.success,
                    extracted_content=json.dumps(output_dict),
                    long_term_memory=f'Task completed. Success Status: {params.success}',
                )

        else:

            @self.registry.action(
                'Complete task - provide a summary of results for the user. Set success=True if task completed successfully, false otherwise. Text should be your response to the user summarizing results. Include files in files_to_display if you would like to display to the user or there files are important for the task result.',
                param_model=DoneAction,
            )
            async def done(params: DoneAction, file_system: CustomFileSystem):
                user_message = params.text

                len_text = len(params.text)
                len_max_memory = 100
                memory = f'Task completed: {params.success} - {params.text[:len_max_memory]}'
                if len_text > len_max_memory:
                    memory += f' - {len_text - len_max_memory} more characters'

                attachments = []
                if params.files_to_display:
                    if self.display_files_in_done_text:
                        file_msg = ''
                        for file_name in params.files_to_display:
                            if file_name == 'todo.md':
                                continue
                            file_content = await file_system.display_file(file_name)
                            if file_content:
                                file_msg += f'\n\n{file_name}:\n{file_content}'
                                attachments.append(file_name)
                        if file_msg:
                            user_message += '\n\nAttachments:'
                            user_message += file_msg
                        else:
                            logger.warning('Agent wanted to display files but none were found')
                    else:
                        for file_name in params.files_to_display:
                            if file_name == 'todo.md':
                                continue
                            file_content = await file_system.display_file(file_name)
                            if file_content:
                                attachments.append(file_name)

                attachments = [file_name for file_name in attachments]

                return ActionResult(
                    is_done=True,
                    success=params.success,
                    extracted_content=user_message,
                    long_term_memory=memory,
                    attachments=attachments,
                )

    def _register_browser_actions(self):
        """Register custom browser actions"""

        @self.registry.action('Upload file to interactive element with file path', param_model=UploadFileAction)
        async def upload_file_to_element(
                params: UploadFileAction, browser_session: BrowserSession, file_system: FileSystem
        ):

            # For local browsers, ensure the file exists on the local filesystem
            full_file_path = params.path
            if not os.path.exists(full_file_path):
                full_file_path = str(file_system.get_dir() / params.path)
            if not os.path.exists(full_file_path):
                msg = f'File {params.path} does not exist'
                return ActionResult(error=msg)

            # Get the selector map to find the node
            selector_map = await browser_session.get_selector_map()
            if params.index not in selector_map:
                msg = f'Element with index {params.index} does not exist.'
                return ActionResult(error=msg)

            node = selector_map[params.index]

            # Helper function to find file input near the selected element
            def find_file_input_near_element(
                    node: EnhancedDOMTreeNode, max_height: int = 3, max_descendant_depth: int = 3
            ) -> EnhancedDOMTreeNode | None:
                """Find the closest file input to the selected element."""

                def find_file_input_in_descendants(n: EnhancedDOMTreeNode, depth: int) -> EnhancedDOMTreeNode | None:
                    if depth < 0:
                        return None
                    if browser_session.is_file_input(n):
                        return n
                    for child in n.children_nodes or []:
                        result = find_file_input_in_descendants(child, depth - 1)
                        if result:
                            return result
                    return None

                current = node
                for _ in range(max_height + 1):
                    # Check the current node itself
                    if browser_session.is_file_input(current):
                        return current
                    # Check all descendants of the current node
                    result = find_file_input_in_descendants(current, max_descendant_depth)
                    if result:
                        return result
                    # Check all siblings and their descendants
                    if current.parent_node:
                        for sibling in current.parent_node.children_nodes or []:
                            if sibling is current:
                                continue
                            if browser_session.is_file_input(sibling):
                                return sibling
                            result = find_file_input_in_descendants(sibling, max_descendant_depth)
                            if result:
                                return result
                    current = current.parent_node
                    if not current:
                        break
                return None

            # Try to find a file input element near the selected element
            file_input_node = find_file_input_near_element(node)

            # If not found near the selected element, fallback to finding the closest file input to current scroll position
            if file_input_node is None:
                logger.info(
                    f'No file upload element found near index {params.index}, searching for closest file input to scroll position'
                )

                # Get current scroll position
                cdp_session = await browser_session.get_or_create_cdp_session()
                try:
                    scroll_info = await cdp_session.cdp_client.send.Runtime.evaluate(
                        params={'expression': 'window.scrollY || window.pageYOffset || 0'},
                        session_id=cdp_session.session_id
                    )
                    current_scroll_y = scroll_info.get('result', {}).get('value', 0)
                except Exception:
                    current_scroll_y = 0

                # Find all file inputs in the selector map and pick the closest one to scroll position
                closest_file_input = None
                min_distance = float('inf')

                for idx, element in selector_map.items():
                    if browser_session.is_file_input(element):
                        # Get element's Y position
                        if element.absolute_position:
                            element_y = element.absolute_position.y
                            distance = abs(element_y - current_scroll_y)
                            if distance < min_distance:
                                min_distance = distance
                                closest_file_input = element

                if closest_file_input:
                    file_input_node = closest_file_input
                    logger.info(f'Found file input closest to scroll position (distance: {min_distance}px)')
                else:
                    msg = 'No file upload element found on the page'
                    logger.error(msg)
                    raise BrowserError(msg)
                # TODO: figure out why this fails sometimes + add fallback hail mary, just look for any file input on page

            # Dispatch upload file event with the file input node
            try:
                event = browser_session.event_bus.dispatch(UploadFileEvent(node=file_input_node, file_path=full_file_path))
                await event
                await event.event_result(raise_if_any=True, raise_if_none=False)
                msg = f'Successfully uploaded file to index {params.index}'
                logger.info(f'📁 {msg}')
                return ActionResult(
                    extracted_content=msg,
                    long_term_memory=f'Uploaded file {params.path} to element {params.index}',
                )
            except Exception as e:
                logger.error(f'Failed to upload file: {e}')
                raise BrowserError(f'Failed to upload file: {e}')

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
            'Take a screenshot of the current page and save it to the file system',
            param_model=NoParamsAction
        )
        async def take_screenshot(_: NoParamsAction, browser_session: AgentBrowserSession, file_system: FileSystem):
            try:
                # Take screenshot using browser session
                screenshot = await browser_session.take_screenshot()

                # Generate timestamp for filename
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

                # Get file system directory path (Path type)
                fs_dir = file_system.get_dir()

                # Create screenshots directory if it doesn't exist
                screenshots_dir = fs_dir / "screenshots"
                screenshots_dir.mkdir(exist_ok=True)

                # Save screenshot to file system
                page_title = await browser_session.get_current_page_title()
                page_title = sanitize_filename(page_title)
                filename = f"{page_title}-{timestamp}.png"
                filepath = screenshots_dir / filename

                with open(filepath, "wb") as f:
                    f.write(base64.b64decode(screenshot))

                msg = f'📸 Screenshot saved to path: {str(filepath.relative_to(fs_dir))}'
                logger.info(msg)
                return ActionResult(
                    extracted_content=msg,
                    include_in_memory=True,
                    long_term_memory=f'Screenshot saved to {str(filepath.relative_to(fs_dir))}',
                )
            except Exception as e:
                error_msg = f'❌ Failed to take screenshot: {str(e)}'
                logger.error(error_msg)
                return ActionResult(error=error_msg)
