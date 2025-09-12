from typing import Any, Generic, TypeVar
from browser_use.tools.registry.service import Registry
from pydantic import BaseModel
import pdb
import os
import asyncio
import json
import enum
import base64
import mimetypes

from typing import Optional, Type, Callable, Dict, Any, Union, Awaitable, TypeVar
from pydantic import BaseModel
from browser_use.tools.service import Controller, Tools
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

logger = get_logger(__name__)

Context = TypeVar('Context')

T = TypeVar('T', bound=BaseModel)


class VibeSurfTools(Generic[Context]):
    def __init__(self, exclude_actions: list[str] = []):
        self.registry = Registry[Context](exclude_actions)
        self._register_file_actions()
        self.mcp_server_config = None
        self.mcp_clients = {}

    def _register_file_actions(self):
        @self.registry.action(
            'Read file content from file system. If this is a file not in current file system, please provide an absolute path.')
        async def read_file(file_name: str, file_system: FileSystem):
            if not os.path.exists(file_name):
                # if not exists, assume it is external_file
                external_file = True
            else:
                external_file = False
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
                    file_path = os.path.join(file_system.get_dir(), file_path)

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

        @self.registry.action(
            'Copy a file to the FileSystem. Set external_src=True to copy from external file system to FileSystem, False to copy within FileSystem.'
        )
        async def copy_file(src_filename: str, dst_filename: str, file_system: CustomFileSystem,
                            external_src: bool = False):
            result = await file_system.copy_file(src_filename, dst_filename, external_src)
            logger.info(f'📁 {result}')
            return ActionResult(
                extracted_content=result,
                include_in_memory=True,
                long_term_memory=result,
            )

        @self.registry.action(
            'Rename a file within the FileSystem from old_filename to new_filename.'
        )
        async def rename_file(old_filename: str, new_filename: str, file_system: CustomFileSystem):
            result = await file_system.rename_file(old_filename, new_filename)
            logger.info(f'📁 {result}')
            return ActionResult(
                extracted_content=result,
                include_in_memory=True,
                long_term_memory=result,
            )

        @self.registry.action(
            'Move a file within the FileSystem from old_filename to new_filename.'
        )
        async def move_file(old_filename: str, new_filename: str, file_system: CustomFileSystem):
            result = await file_system.move_file(old_filename, new_filename)
            logger.info(f'📁 {result}')
            return ActionResult(
                extracted_content=result,
                include_in_memory=True,
                long_term_memory=result,
            )

    async def register_mcp_clients(self, mcp_server_config: Optional[Dict[str, Any]] = None):
        self.mcp_server_config = mcp_server_config or self.mcp_server_config
        if self.mcp_server_config:
            await self.unregister_mcp_clients()
            await self.register_mcp_tools()

    async def register_mcp_tools(self):
        """
        Register the MCP tools used by this tools.
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
                client = CustomMCPClient(
                    server_name=server_name,
                    command=server_config['command'],
                    args=server_config['args'],
                    env=server_config.get('env', None)
                )

                # Connect to the MCP server
                await client.connect(timeout=200)

                # Register tools to tools with prefix
                prefix = f"mcp.{server_name}."
                await client.register_to_tools(
                    tools=self,
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
