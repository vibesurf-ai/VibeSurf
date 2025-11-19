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
    SearchAction,
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
from vibe_surf.tools.views import HoverAction, ExtractionAction, FileExtractionAction, DownloadMediaAction
from vibe_surf.tools.mcp_client import CustomMCPClient
from vibe_surf.tools.file_system import CustomFileSystem
from vibe_surf.logger import get_logger
from vibe_surf.tools.vibesurf_tools import VibeSurfTools
from vibe_surf.tools.views import GenJSCodeAction

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
            '',
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
                with open(code_file, "w") as f:
                    await file_system.write_file(code_file, execute_result)

                if len(execute_result) < 1000:
                    msg = f'JavaScript Code save at:{code_file}\nResult:\n```json\n {execute_result}\n```\n'
                else:
                    result_file = f"codes/{timestamp}.json"
                    await file_system.write_file(result_file, execute_result)
                    msg = f'JavaScript Code save at:{code_file}\nResult:\n```json\n {execute_result[:1000]}\n...TRUNCATED...\n```\nView more in {result_file}\n'
                if success:
                    return ActionResult(extracted_content=msg)
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
            param_model=NoParamsAction
        )
        async def take_screenshot(_: NoParamsAction, browser_session: AgentBrowserSession, file_system: FileSystem):
            try:
                # Take screenshot using browser session
                screenshot_bytes = await browser_session.take_screenshot()

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
                async with aiohttp.ClientSession() as session:
                    async with session.get(params.url) as response:
                        if response.status != 200:
                            raise Exception(f"HTTP {response.status}: Failed to download from {params.url}")

                        # Get content
                        content = await response.read()
                        headers_dict = dict(response.headers)
                        # Detect file format and extension
                        file_extension = await self._detect_file_format(params.url, headers_dict, content)

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
                        size_str = self._format_file_size(file_size)

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

    async def _detect_file_format(self, url: str, headers: dict, content: bytes) -> str:
        """Detect file format from URL, headers, and content"""

        # Try Content-Type header first
        content_type = headers.get('content-type', '').lower()
        if content_type:
            # Common image formats
            if 'image/jpeg' in content_type or 'image/jpg' in content_type:
                return '.jpg'
            elif 'image/png' in content_type:
                return '.png'
            elif 'image/gif' in content_type:
                return '.gif'
            elif 'image/webp' in content_type:
                return '.webp'
            elif 'image/svg' in content_type:
                return '.svg'
            elif 'image/bmp' in content_type:
                return '.bmp'
            elif 'image/tiff' in content_type:
                return '.tiff'
            # Video formats
            elif 'video/mp4' in content_type:
                return '.mp4'
            elif 'video/webm' in content_type:
                return '.webm'
            elif 'video/avi' in content_type:
                return '.avi'
            elif 'video/mov' in content_type or 'video/quicktime' in content_type:
                return '.mov'
            # Audio formats
            elif 'audio/mpeg' in content_type or 'audio/mp3' in content_type:
                return '.mp3'
            elif 'audio/wav' in content_type:
                return '.wav'
            elif 'audio/ogg' in content_type:
                return '.ogg'
            elif 'audio/webm' in content_type:
                return '.webm'

        # Try magic number detection
        if len(content) >= 8:
            # JPEG
            if content.startswith(b'\xff\xd8\xff'):
                return '.jpg'
            # PNG
            elif content.startswith(b'\x89PNG\r\n\x1a\n'):
                return '.png'
            # GIF
            elif content.startswith(b'GIF87a') or content.startswith(b'GIF89a'):
                return '.gif'
            # WebP
            elif content[8:12] == b'WEBP':
                return '.webp'
            # BMP
            elif content.startswith(b'BM'):
                return '.bmp'
            # TIFF
            elif content.startswith(b'II*\x00') or content.startswith(b'MM\x00*'):
                return '.tiff'
            # MP4
            elif b'ftyp' in content[4:12]:
                return '.mp4'
            # PDF
            elif content.startswith(b'%PDF'):
                return '.pdf'

        # Try URL path extension
        url_path = urllib.parse.urlparse(url).path
        if url_path:
            ext = os.path.splitext(url_path)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp', '.tiff',
                       '.mp4', '.webm', '.avi', '.mov', '.wmv', '.flv',
                       '.mp3', '.wav', '.ogg', '.aac', '.flac',
                       '.pdf', '.doc', '.docx', '.txt']:
                return ext

        # Default fallback
        return '.bin'

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024.0 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        return f"{size_bytes:.1f} {size_names[i]}"
