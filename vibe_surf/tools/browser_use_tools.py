import pdb
import os
import asyncio
import json
import enum
import base64
import mimetypes
import datetime
import aiohttp
import re
import urllib.parse
from pathvalidate import sanitize_filename
from typing import Optional, Type, Callable, Dict, Any, Union, Awaitable, TypeVar
from pydantic import BaseModel
from browser_use.tools.service import Tools, ScrollEvent
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
    SelectDropdownOptionAction,
    SendKeysAction,
    StructuredOutputAction,
    SwitchTabAction,
    UploadFileAction,
    NavigateAction
)
from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import UserMessage, ContentPartTextParam, ContentPartImageParam, ImageURL
from browser_use.dom.service import EnhancedDOMTreeNode
from browser_use.browser.views import BrowserError
from browser_use.mcp.client import MCPClient

from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.tools.views import SearchAction, HoverAction, ExtractionAction, FileExtractionAction, DownloadMediaAction, TakeScreenshotAction
from vibe_surf.tools.mcp_client import CustomMCPClient
from vibe_surf.tools.file_system import CustomFileSystem
from vibe_surf.logger import get_logger
from vibe_surf.tools.vibesurf_tools import VibeSurfTools
from vibe_surf.tools.views import GenJSCodeAction
from vibe_surf.tools.utils import _detect_file_format, _format_file_size

logger = get_logger(__name__)

# Global storage for console logs (keyed by session_id)
_console_logs_storage: Dict[str, list] = {}

# Global storage for network logs (keyed by session_id)
_network_logs_storage: Dict[str, dict] = {}

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
                'Complete task with structured output.',
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
                'Complete task.',
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

        @self.registry.action(
            "",
            param_model=ScrollAction,
        )
        async def scroll(params: ScrollAction, browser_session: BrowserSession):
            try:
                # Look up the node from the selector map if index is provided
                # Special case: index 0 means scroll the whole page (root/body element)
                node = None
                if params.index is not None and params.index != 0:
                    node = await browser_session.get_element_by_index(params.index)
                    if node is None:
                        # Element does not exist
                        msg = f'Element index {params.index} not found in browser state'
                        return ActionResult(error=msg)

                direction = 'down' if params.down else 'up'
                target = f'element {params.index}' if params.index is not None and params.index != 0 else ''

                # Get actual viewport height for more accurate scrolling
                try:
                    cdp_session = await browser_session.get_or_create_cdp_session()
                    metrics = await cdp_session.cdp_client.send.Page.getLayoutMetrics(session_id=cdp_session.session_id)

                    # Use cssVisualViewport for the most accurate representation
                    css_viewport = metrics.get('cssVisualViewport', {})
                    css_layout_viewport = metrics.get('cssLayoutViewport', {})

                    # Get viewport height, prioritizing cssVisualViewport
                    viewport_height = int(
                        css_viewport.get('clientHeight') or css_layout_viewport.get('clientHeight', 1000))

                    logger.debug(f'Detected viewport height: {viewport_height}px')
                except Exception as e:
                    viewport_height = 1000  # Fallback to 1000px
                    logger.debug(f'Failed to get viewport height, using fallback 1000px: {e}')

                # For multiple pages (>=1.0), scroll one page at a time to ensure each scroll completes
                if params.pages >= 1.0:
                    import asyncio

                    num_full_pages = int(params.pages)
                    remaining_fraction = params.pages - num_full_pages

                    completed_scrolls = 0

                    # Scroll one page at a time
                    for i in range(num_full_pages):
                        try:
                            pixels = viewport_height  # Use actual viewport height
                            if not params.down:
                                pixels = -pixels

                            event = browser_session.event_bus.dispatch(
                                ScrollEvent(direction=direction, amount=abs(pixels), node=node)
                            )
                            await event
                            await event.event_result(raise_if_any=True, raise_if_none=False)
                            completed_scrolls += 1

                            # Small delay to ensure scroll completes before next one
                            await asyncio.sleep(0.15)

                        except Exception as e:
                            logger.warning(f'Scroll {i + 1}/{num_full_pages} failed: {e}')
                            break
                        # Continue with remaining scrolls even if one fails

                    # Handle fractional page if present
                    if remaining_fraction > 0:
                        try:
                            pixels = int(remaining_fraction * viewport_height)
                            if not params.down:
                                pixels = -pixels

                            event = browser_session.event_bus.dispatch(
                                ScrollEvent(direction=direction, amount=abs(pixels), node=node)
                            )
                            await event
                            await event.event_result(raise_if_any=True, raise_if_none=False)
                            completed_scrolls += remaining_fraction

                        except Exception as e:
                            logger.warning(f'Fractional scroll failed: {e}')

                    if params.pages == 1.0:
                        long_term_memory = f'Scrolled {direction} {target} {viewport_height}px'.replace('  ', ' ')
                    else:
                        long_term_memory = f'Scrolled {direction} {target} {completed_scrolls:.1f} pages'.replace('  ',
                                                                                                                  ' ')
                else:
                    # For fractional pages <1.0, do single scroll
                    pixels = int(params.pages * viewport_height)
                    event = browser_session.event_bus.dispatch(
                        ScrollEvent(direction='down' if params.down else 'up', amount=pixels, node=node)
                    )
                    await event
                    await event.event_result(raise_if_any=True, raise_if_none=False)
                    long_term_memory = f'Scrolled {direction} {target} {params.pages} pages'.replace('  ', ' ')

                msg = f'🔍 {long_term_memory}'
                logger.info(msg)
                return ActionResult(extracted_content=msg, long_term_memory=long_term_memory)
            except Exception as e:
                logger.error(f'Failed to dispatch ScrollEvent: {type(e).__name__}: {e}')
                error_msg = 'Failed to execute scroll action.'
                return ActionResult(error=error_msg)

        @self.registry.action(
            'Hover on an element.',
            param_model=HoverAction,
        )
        async def hover(params: HoverAction, browser_session: AgentBrowserSession):
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
            '',
            param_model=SearchAction,
        )
        async def search(params: SearchAction, browser_session: AgentBrowserSession):
            import urllib.parse

            # Encode query for URL safety
            encoded_query = urllib.parse.quote_plus(params.query)

            # Build search URL based on search engine
            search_engines = {
                'duckduckgo': f'https://duckduckgo.com/?q={encoded_query}',
                'google': f'https://www.google.com/search?q={encoded_query}&udm=14',
                'bing': f'https://www.bing.com/search?q={encoded_query}',
            }

            if params.engine.lower() not in search_engines:
                return ActionResult(
                    error=f'Unsupported search engine: {params.engine}. Options: duckduckgo, google, bing')

            search_url = search_engines[params.engine.lower()]

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
            '',
            param_model=NavigateAction
        )
        async def navigate(params: NavigateAction, browser_session: AgentBrowserSession):
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
            'Generate JavaScript code via LLM and Execute on webpage. Useful for crawl web data and process.',
            param_model=GenJSCodeAction,
        )
        async def gen_and_execute_js_code(
                params: GenJSCodeAction,
                browser_session: AgentBrowserSession,
                page_extraction_llm: BaseChatModel,
                file_system: FileSystem
        ):
            try:
                if not page_extraction_llm:
                    raise RuntimeError("LLM is required for skill_code")

                from vibe_surf.tools.utils import generate_java_script_code

                success, execute_result, js_code = await generate_java_script_code(params.code_requirement,
                                                                                   page_extraction_llm, browser_session,
                                                                                   MAX_ITERATIONS=5)
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                code_file = f"codes/{timestamp}.js"
                await file_system.write_file(code_file, js_code)

                if len(execute_result) < 1000:
                    msg = f'JavaScript Code save at:{code_file}\nResult:\n```json\n {execute_result}\n```\n'
                else:
                    result_file = f"codes/{timestamp}.json"
                    await file_system.write_file(result_file, execute_result)
                    msg = f'Code save at:{code_file}\n```javascript\n{js_code}\n```\n Result save at {result_file}:\n```json\n {execute_result[:1000]}\n...\n```'
                if success:
                    return ActionResult(extracted_content=msg, include_in_memory=True)
                else:
                    return ActionResult(error=msg)
            except Exception as e:
                logger.error(f'❌ Skill Code failed: {e}')
                return ActionResult(error=f'Skill code failed: {str(e)}')

        @self.registry.action(
            '',
            param_model=NoParamsAction
        )
        async def go_back(_: NoParamsAction, browser_session: AgentBrowserSession):
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
            'Take a screenshot of the current page and save it to the file system',
            param_model=TakeScreenshotAction
        )
        async def screenshot(params: TakeScreenshotAction, browser_session: AgentBrowserSession, file_system: FileSystem):
            try:
                # Take screenshot using browser session
                screenshot_bytes = await browser_session.take_screenshot()

                # Apply crop if all crop parameters are provided
                if params.crop_x1 is not None and params.crop_y1 is not None and params.crop_x2 is not None and params.crop_y2 is not None:
                    from io import BytesIO
                    from PIL import Image

                    # Open image with PIL
                    image = Image.open(BytesIO(screenshot_bytes))
                    width, height = image.size

                    # Convert relative coordinates (0-1) to pixel coordinates
                    x1 = int(params.crop_x1 * width)
                    y1 = int(params.crop_y1 * height)
                    x2 = int(params.crop_x2 * width)
                    y2 = int(params.crop_y2 * height)

                    # Validate crop coordinates
                    if x1 >= x2 or y1 >= y2:
                        return ActionResult(error=f'Invalid crop coordinates: x1={x1}, y1={y1}, x2={x2}, y2={y2}')

                    # Crop the image
                    cropped_image = image.crop((x1, y1, x2, y2))

                    # Save cropped image to bytes
                    output = BytesIO()
                    cropped_image.save(output, format='PNG')
                    screenshot_bytes = output.getvalue()

                    logger.info(f'Cropped screenshot: {x1},{y1},{x2},{y2} from {width}x{height}')

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

                # Add crop suffix to filename if cropped
                crop_suffix = ""
                if params.crop_x1 is not None:
                    crop_suffix = f"_crop_{params.crop_x1}_{params.crop_y1}_{params.crop_x2}_{params.crop_y2}"

                filename = f"{page_title}-{timestamp}{crop_suffix}.png"
                filepath = screenshots_dir / filename

                with open(filepath, "wb") as f:
                    f.write(screenshot_bytes)

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

        @self.registry.action(
            'Download media from URL and save to filesystem downloads folder',
            param_model=DownloadMediaAction
        )
        async def download_media(params: DownloadMediaAction, file_system: FileSystem):
            """Download media from URL with automatic file format detection"""
            try:
                # Get file system directory path (Path type)
                fs_dir = file_system.get_dir()

                # Create downloads directory if it doesn't exist
                downloads_dir = fs_dir / "downloads"
                downloads_dir.mkdir(exist_ok=True)

                # Download the file and detect format
                async with aiohttp.ClientSession(trust_env=True) as session:
                    async with session.get(params.url) as response:
                        if response.status != 200:
                            raise Exception(f"HTTP {response.status}: Failed to download from {params.url}")

                        # Get content
                        content = await response.read()
                        headers_dict = dict(response.headers)
                        # Detect file format and extension
                        file_extension = await _detect_file_format(params.url, headers_dict, content)

                        # Generate filename
                        if params.filename:
                            # Use provided filename, add extension if missing
                            filename = params.filename
                            if not filename.endswith(file_extension):
                                filename = f"{filename}{file_extension}"
                        else:
                            # Generate filename from URL or timestamp
                            url_path = urllib.parse.urlparse(params.url).path
                            url_filename = os.path.basename(url_path)

                            if url_filename and not url_filename.startswith('.'):
                                # Use URL filename, ensure correct extension
                                filename = url_filename
                                if not filename.endswith(file_extension):
                                    base_name = os.path.splitext(filename)[0]
                                    filename = f"{base_name}{file_extension}"
                            else:
                                # Generate timestamp-based filename
                                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                                filename = f"media_{timestamp}{file_extension}"

                        # Sanitize filename
                        filename = sanitize_filename(filename)
                        filepath = downloads_dir / filename

                        # Save file
                        with open(filepath, "wb") as f:
                            f.write(content)

                        # Calculate file size for display
                        file_size = len(content)
                        size_str = _format_file_size(file_size)

                        msg = f'📥 Downloaded media to: {str(filepath.relative_to(fs_dir))} ({size_str})'
                        logger.info(msg)
                        return ActionResult(
                            extracted_content=msg,
                            include_in_memory=True,
                            long_term_memory=f'Downloaded media from {params.url} to {str(filepath.relative_to(fs_dir))}',
                        )

            except Exception as e:
                error_msg = f'❌ Failed to download media: {str(e)}'
                logger.error(error_msg)
                return ActionResult(error=error_msg)

        @self.registry.action(
            'Get HTML content of current page and save to file',
            param_model=NoParamsAction
        )
        async def get_html_content(_: NoParamsAction, browser_session: AgentBrowserSession, file_system: FileSystem):
            """Get HTML content of current page and save to file"""
            try:
                # Wait for stable network
                await browser_session._wait_for_stable_network(max_attempt=3)

                # Get HTML content
                html_content = await browser_session.get_html_content()

                # Get file system directory
                fs_dir = file_system.get_dir()

                # Create htmls directory if it doesn't exist
                htmls_dir = fs_dir / "htmls"
                htmls_dir.mkdir(exist_ok=True)

                # Generate filename with timestamp
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                page_title = await browser_session.get_current_page_title()
                page_title = sanitize_filename(page_title)
                filename = f"{page_title}-{timestamp}.html"
                filepath = htmls_dir / filename

                # Save HTML content
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(html_content)

                msg = f'📄 HTML content saved to: {str(filepath.relative_to(fs_dir))}'
                logger.info(msg)
                return ActionResult(
                    extracted_content=msg,
                    include_in_memory=True,
                    long_term_memory=f'Saved HTML content to {str(filepath.relative_to(fs_dir))}',
                )
            except Exception as e:
                error_msg = f'❌ Failed to get HTML content: {str(e)}'
                logger.error(error_msg)
                return ActionResult(error=error_msg)

        @self.registry.action(
            'Refresh current page',
            param_model=NoParamsAction
        )
        async def reload_page(_: NoParamsAction, browser_session: AgentBrowserSession):
            """Reload the current page"""
            try:
                page = await browser_session.get_current_page()
                await page.reload()

                memory = 'Page reloaded'
                msg = f'🔄 {memory}'
                logger.info(msg)
                return ActionResult(extracted_content=memory, include_in_memory=True, long_term_memory=memory)
            except Exception as e:
                error_msg = f'❌ Failed to reload page: {str(e)}'
                logger.error(error_msg)
                return ActionResult(error=error_msg)

        @self.registry.action(
            'Start monitoring browser console logs (console.log, console.warn, console.error, etc.)',
            param_model=NoParamsAction
        )
        async def start_console_logging(_: NoParamsAction, browser_session: AgentBrowserSession):
            """
            Start monitoring console logs from the browser.

            This enables the CDP Console domain and registers an event handler
            to collect all console messages (log, warn, error, info, debug, etc.).
            """
            try:
                # Get CDP session
                cdp_session = await browser_session.get_or_create_cdp_session()
                session_id = cdp_session.session_id

                # Initialize storage for this session
                _console_logs_storage[session_id] = []

                # Define the callback function for console messages
                def on_console_message(event_data: dict, event_session_id: Optional[str]):
                    """Callback to collect console messages"""
                    message = event_data.get('message', {})
                    log_entry = {
                        'source': message.get('source', ''),
                        'level': message.get('level', ''),
                        'text': message.get('text', ''),
                        'url': message.get('url', ''),
                        'line': message.get('line', 0),
                        'column': message.get('column', 0),
                        'timestamp': asyncio.get_event_loop().time()
                    }
                    _console_logs_storage[session_id].append(log_entry)
                    logger.debug(f"Console [{log_entry['level']}]: {log_entry['text']}")

                # Register the event handler
                cdp_session.cdp_client.register.Console.messageAdded(on_console_message)

                # Enable Console domain to start receiving messages
                await cdp_session.cdp_client.send.Console.enable(session_id=session_id)

                memory = f"Console logging started (session: {session_id[:8]}...)"
                msg = f'🎯 {memory}'
                logger.info(msg)
                return ActionResult(extracted_content=memory, include_in_memory=True, long_term_memory=memory)

            except Exception as e:
                error_msg = f"❌ Failed to start console logging: {str(e)}"
                logger.error(error_msg)
                return ActionResult(error=error_msg)

        @self.registry.action(
            'Stop console logging and retrieve all collected console messages',
            param_model=NoParamsAction
        )
        async def stop_console_logging(_: NoParamsAction, browser_session: AgentBrowserSession, file_system: FileSystem):
            """
            Stop monitoring console logs and return all collected logs.

            This disables the Console domain, unregisters the event handler,
            saves all console messages to a file, and returns a summary.

            Returns logs as a formatted string with each entry showing:
            - Log level (log/warn/error/info/debug)
            - Message text
            - Source location (file, line, column) if available
            """
            try:
                # Get CDP session
                cdp_session = await browser_session.get_or_create_cdp_session()
                session_id = cdp_session.session_id

                # Disable Console domain
                await cdp_session.cdp_client.send.Console.disable(session_id=session_id)

                # Unregister the event handler
                cdp_session.cdp_client._event_registry.unregister("Console.messageAdded")

                # Retrieve and clear the logs for this session
                logs = _console_logs_storage.get(session_id, [])
                if session_id in _console_logs_storage:
                    del _console_logs_storage[session_id]

                # Handle no logs case
                if not logs:
                    memory = "No console logs were captured"
                    msg = f'📋 {memory}'
                    logger.info(msg)
                    return ActionResult(
                        extracted_content=memory,
                        include_in_memory=True,
                        long_term_memory=memory
                    )

                # Group logs by level
                log_counts = {}
                for log in logs:
                    level = log['level']
                    log_counts[level] = log_counts.get(level, 0) + 1

                # Format detailed logs
                log_lines = []
                for i, log in enumerate(logs, 1):
                    location = ""
                    if log.get('url'):
                        location = f" ({log['url']}"
                        if log.get('line'):
                            location += f":{log['line']}"
                            if log.get('column'):
                                location += f":{log['column']}"
                        location += ")"

                    log_lines.append(f"{i}. [{log['level'].upper()}] {log['text']}{location}")

                # Save logs to file
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                fs_dir = file_system.get_dir()
                console_dir = fs_dir / "console"
                console_dir.mkdir(exist_ok=True)

                page_title = await browser_session.get_current_page_title()
                page_title = sanitize_filename(page_title)
                console_filename = f"{page_title}-{timestamp}.log"
                console_filepath = console_dir / console_filename

                # Write full logs to file
                full_logs_text = "\n".join(log_lines)
                with open(console_filepath, 'w', encoding='utf-8') as f:
                    f.write(f"Console Logs Captured at {timestamp}\n")
                    f.write("=" * 80 + "\n\n")
                    f.write(full_logs_text)

                # Also save as JSON for structured access
                json_filename = f"{page_title}-{timestamp}.json"
                json_filepath = console_dir / json_filename
                with open(json_filepath, 'w', encoding='utf-8') as f:
                    json.dump(logs, f, indent=2, ensure_ascii=False)

                # Build summary
                summary_parts = [f"{count} {level}" for level, count in sorted(log_counts.items())]
                summary = f"Collected {len(logs)} console messages: {', '.join(summary_parts)}\n"
                summary += f"Logs saved to: {str(console_filepath.relative_to(fs_dir))}\n"
                summary += f"JSON saved to: {str(json_filepath.relative_to(fs_dir))}"

                # Create a truncated preview (max 10 logs)
                preview_limit = 10
                if len(logs) > preview_limit:
                    preview_lines = log_lines[:preview_limit]
                    preview_text = "\n".join(preview_lines)
                    preview_text += f"\n\n... and {len(logs) - preview_limit} more logs (see file for full details)"
                    extracted_content = f"{summary}\n\nPreview (first {preview_limit} logs):\n{preview_text}"
                else:
                    logs_text = "\n".join(log_lines)
                    extracted_content = f"{summary}\n\nConsole Logs:\n{logs_text}"

                msg = f'📋 Collected {len(logs)} console messages: {", ".join(summary_parts)}'
                logger.info(msg)
                logger.info(f'Console logs saved to: {str(console_filepath.relative_to(fs_dir))}')
                logger.info(f'Console JSON saved to: {str(json_filepath.relative_to(fs_dir))}')

                return ActionResult(
                    extracted_content=extracted_content,
                    include_in_memory=True,
                    long_term_memory=f"Retrieved {len(logs)} console log entries, saved to {str(console_filepath.relative_to(fs_dir))}"
                )

            except Exception as e:
                error_msg = f"❌ Failed to stop console logging: {str(e)}"
                logger.error(error_msg)
                # Still try to return any logs we have
                try:
                    session_id = cdp_session.session_id if cdp_session else None
                    logs = _console_logs_storage.get(session_id, []) if session_id else []
                    if session_id and session_id in _console_logs_storage:
                        del _console_logs_storage[session_id]

                    if logs:
                        error_msg += f"\n\nPartially retrieved {len(logs)} logs before error"
                except:
                    pass

                return ActionResult(error=error_msg)

        @self.registry.action(
            'Start monitoring network traffic (HTTP requests, responses, timing, headers, etc.)',
            param_model=NoParamsAction
        )
        async def start_network_logging(_: NoParamsAction, browser_session: AgentBrowserSession):
            """
            Start monitoring network traffic from the browser.

            This enables the CDP Network domain and registers event handlers
            to collect all network requests, responses, and timing information.
            """
            try:
                # Get CDP session
                cdp_session = await browser_session.get_or_create_cdp_session()
                session_id = cdp_session.session_id

                # Initialize storage for this session
                _network_logs_storage[session_id] = {
                    'requests': {},  # keyed by requestId
                    'start_time': asyncio.get_event_loop().time()
                }

                # Define callback functions for network events
                def on_request_will_be_sent(event_data: dict, event_session_id: Optional[str]):
                    """Callback for requestWillBeSent event"""
                    request_id = event_data.get('requestId')
                    if session_id in _network_logs_storage and request_id:
                        request = event_data.get('request', {})
                        _network_logs_storage[session_id]['requests'][request_id] = {
                            'requestId': request_id,
                            'url': request.get('url', ''),
                            'method': request.get('method', ''),
                            'headers': request.get('headers', {}),
                            'postData': request.get('postData'),
                            'timestamp': event_data.get('timestamp'),
                            'wallTime': event_data.get('wallTime'),
                            'type': event_data.get('type', ''),
                            'initiator': event_data.get('initiator', {}),
                            'documentURL': event_data.get('documentURL', ''),
                        }
                        logger.debug(f"Network request: {request.get('method')} {request.get('url')}")

                def on_response_received(event_data: dict, event_session_id: Optional[str]):
                    """Callback for responseReceived event"""
                    request_id = event_data.get('requestId')
                    if session_id in _network_logs_storage and request_id:
                        if request_id in _network_logs_storage[session_id]['requests']:
                            response = event_data.get('response', {})
                            _network_logs_storage[session_id]['requests'][request_id].update({
                                'response': {
                                    'status': response.get('status'),
                                    'statusText': response.get('statusText', ''),
                                    'headers': response.get('headers', {}),
                                    'mimeType': response.get('mimeType', ''),
                                    'connectionReused': response.get('connectionReused', False),
                                    'connectionId': response.get('connectionId', 0),
                                    'encodedDataLength': response.get('encodedDataLength', 0),
                                    'fromDiskCache': response.get('fromDiskCache', False),
                                    'fromServiceWorker': response.get('fromServiceWorker', False),
                                    'timing': response.get('timing'),
                                },
                                'responseTimestamp': event_data.get('timestamp'),
                            })
                            logger.debug(f"Network response: {response.get('status')} {response.get('url', '')}")

                def on_loading_finished(event_data: dict, event_session_id: Optional[str]):
                    """Callback for loadingFinished event"""
                    request_id = event_data.get('requestId')
                    if session_id in _network_logs_storage and request_id:
                        if request_id in _network_logs_storage[session_id]['requests']:
                            _network_logs_storage[session_id]['requests'][request_id].update({
                                'finished': True,
                                'finishedTimestamp': event_data.get('timestamp'),
                                'encodedDataLength': event_data.get('encodedDataLength', 0),
                            })

                def on_loading_failed(event_data: dict, event_session_id: Optional[str]):
                    """Callback for loadingFailed event"""
                    request_id = event_data.get('requestId')
                    if session_id in _network_logs_storage and request_id:
                        if request_id in _network_logs_storage[session_id]['requests']:
                            _network_logs_storage[session_id]['requests'][request_id].update({
                                'failed': True,
                                'errorText': event_data.get('errorText', ''),
                                'canceled': event_data.get('canceled', False),
                                'blockedReason': event_data.get('blockedReason'),
                            })

                # Register all event handlers
                cdp_session.cdp_client.register.Network.requestWillBeSent(on_request_will_be_sent)
                cdp_session.cdp_client.register.Network.responseReceived(on_response_received)
                cdp_session.cdp_client.register.Network.loadingFinished(on_loading_finished)
                cdp_session.cdp_client.register.Network.loadingFailed(on_loading_failed)

                # Enable Network domain to start receiving events
                await cdp_session.cdp_client.send.Network.enable(session_id=session_id)

                memory = f"Network logging started (session: {session_id[:8]}...)"
                msg = f'🌐 {memory}'
                logger.info(msg)
                return ActionResult(extracted_content=memory, include_in_memory=True, long_term_memory=memory)

            except Exception as e:
                error_msg = f"❌ Failed to start network logging: {str(e)}"
                logger.error(error_msg)
                return ActionResult(error=error_msg)

        @self.registry.action(
            'Stop network logging and retrieve collected traffic data in HAR format',
            param_model=NoParamsAction
        )
        async def stop_network_logging(_: NoParamsAction, browser_session: AgentBrowserSession, file_system: FileSystem):
            """
            Stop monitoring network traffic and return collected data in HAR format.

            This disables the Network domain, unregisters event handlers,
            and returns all network traffic collected since start_network_logging was called.
            The data is saved as a HAR (HTTP Archive) file and a summary is provided.
            """
            try:
                # Get CDP session
                cdp_session = await browser_session.get_or_create_cdp_session()
                session_id = cdp_session.session_id

                # Disable Network domain
                await cdp_session.cdp_client.send.Network.disable(session_id=session_id)

                # Unregister all event handlers
                cdp_session.cdp_client._event_registry.unregister("Network.requestWillBeSent")
                cdp_session.cdp_client._event_registry.unregister("Network.responseReceived")
                cdp_session.cdp_client._event_registry.unregister("Network.loadingFinished")
                cdp_session.cdp_client._event_registry.unregister("Network.loadingFailed")

                # Retrieve network logs
                network_data = _network_logs_storage.get(session_id, {})
                requests_dict = network_data.get('requests', {})
                requests = list(requests_dict.values())

                # Clean up storage
                if session_id in _network_logs_storage:
                    del _network_logs_storage[session_id]

                if not requests:
                    memory = "No network requests were captured"
                    msg = f'📊 {memory}'
                    logger.info(msg)
                    return ActionResult(extracted_content=memory, include_in_memory=True, long_term_memory=memory)

                # Build HAR format
                har_log = {
                    "log": {
                        "version": "1.2",
                        "creator": {
                            "name": "VibeSurf CDP Network Monitor",
                            "version": "1.0"
                        },
                        "pages": [],
                        "entries": []
                    }
                }

                # Convert requests to HAR entries
                for req in requests:
                    # Build HAR entry
                    entry = {
                        "startedDateTime": datetime.datetime.fromtimestamp(req.get('wallTime', 0)).isoformat() + 'Z',
                        "time": 0,  # Will calculate if timing info available
                        "request": {
                            "method": req.get('method', 'GET'),
                            "url": req.get('url', ''),
                            "httpVersion": "HTTP/1.1",
                            "headers": [{"name": k, "value": v} for k, v in req.get('headers', {}).items()],
                            "queryString": [],
                            "headersSize": -1,
                            "bodySize": len(req.get('postData', '')) if req.get('postData') else 0,
                        },
                        "response": {
                            "status": 0,
                            "statusText": "",
                            "httpVersion": "HTTP/1.1",
                            "headers": [],
                            "content": {
                                "size": 0,
                                "mimeType": "text/plain"
                            },
                            "redirectURL": "",
                            "headersSize": -1,
                            "bodySize": -1,
                        },
                        "cache": {},
                        "timings": {
                            "send": 0,
                            "wait": 0,
                            "receive": 0,
                        }
                    }

                    # Add POST data if present
                    if req.get('postData'):
                        entry['request']['postData'] = {
                            "mimeType": "application/x-www-form-urlencoded",
                            "text": req.get('postData')
                        }

                    # Add response data if available
                    if 'response' in req:
                        resp = req['response']
                        entry['response'].update({
                            "status": resp.get('status', 0),
                            "statusText": resp.get('statusText', ''),
                            "headers": [{"name": k, "value": v} for k, v in resp.get('headers', {}).items()],
                            "content": {
                                "size": resp.get('encodedDataLength', 0),
                                "mimeType": resp.get('mimeType', 'text/plain')
                            }
                        })

                        # Add timing if available
                        if resp.get('timing'):
                            timing = resp['timing']
                            entry['timings'] = {
                                "blocked": timing.get('dnsStart', 0),
                                "dns": timing.get('dnsEnd', 0) - timing.get('dnsStart', 0) if timing.get('dnsEnd') else 0,
                                "connect": timing.get('connectEnd', 0) - timing.get('connectStart', 0) if timing.get('connectEnd') else 0,
                                "send": timing.get('sendEnd', 0) - timing.get('sendStart', 0) if timing.get('sendEnd') else 0,
                                "wait": timing.get('receiveHeadersEnd', 0) - timing.get('sendEnd', 0) if timing.get('receiveHeadersEnd') else 0,
                                "receive": 0,
                                "ssl": timing.get('sslEnd', 0) - timing.get('sslStart', 0) if timing.get('sslEnd') and timing.get('sslStart') else -1,
                            }
                            entry['time'] = timing.get('receiveHeadersEnd', 0)

                    har_log['log']['entries'].append(entry)

                # Generate statistics
                total_requests = len(requests)
                successful_requests = sum(1 for r in requests if r.get('finished') and not r.get('failed'))
                failed_requests = sum(1 for r in requests if r.get('failed'))
                methods = {}
                types = {}

                for req in requests:
                    method = req.get('method', 'GET')
                    methods[method] = methods.get(method, 0) + 1
                    req_type = req.get('type', 'other')
                    types[req_type] = types.get(req_type, 0) + 1

                # Save HAR file
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                fs_dir = file_system.get_dir()
                network_dir = fs_dir / "network"
                network_dir.mkdir(exist_ok=True)

                page_title = await browser_session.get_current_page_title()
                page_title = sanitize_filename(page_title)
                har_filename = f"{page_title}-{timestamp}.har"
                har_filepath = network_dir / har_filename

                with open(har_filepath, 'w', encoding='utf-8') as f:
                    json.dump(har_log, f, indent=2)

                # Build summary
                method_summary = ', '.join([f"{count} {method}" for method, count in sorted(methods.items())])
                type_summary = ', '.join([f"{count} {t}" for t, count in sorted(types.items()) if count > 0])

                summary = f"Captured {total_requests} network requests ({successful_requests} successful, {failed_requests} failed)\n"
                summary += f"Methods: {method_summary}\n"
                if type_summary:
                    summary += f"Types: {type_summary}\n"
                summary += f"HAR file saved to: {str(har_filepath.relative_to(fs_dir))}"

                msg = f'📊 Network logging stopped: {total_requests} requests captured'
                logger.info(msg)
                logger.info(f'HAR file saved to: {str(har_filepath.relative_to(fs_dir))}')

                return ActionResult(
                    extracted_content=summary,
                    include_in_memory=True,
                    long_term_memory=f"Captured {total_requests} network requests, saved to {str(har_filepath.relative_to(fs_dir))}"
                )

            except Exception as e:
                error_msg = f"❌ Failed to stop network logging: {str(e)}"
                logger.error(error_msg)
                # Still try to clean up storage
                try:
                    session_id = cdp_session.session_id if cdp_session else None
                    if session_id and session_id in _network_logs_storage:
                        del _network_logs_storage[session_id]
                except:
                    pass

                return ActionResult(error=error_msg)