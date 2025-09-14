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
from datetime import datetime
from typing import Optional, Type, Callable, Dict, Any, Union, Awaitable, TypeVar
from pydantic import BaseModel
from browser_use.tools.service import Controller, Tools, handle_browser_error
import logging
from browser_use.agent.views import ActionModel, ActionResult
from browser_use.utils import time_execution_sync
from browser_use.filesystem.file_system import FileSystem
from browser_use.browser import BrowserSession
from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import UserMessage, ContentPartTextParam, ContentPartImageParam, ImageURL
from browser_use.dom.service import EnhancedDOMTreeNode
from browser_use.browser.views import BrowserError
from browser_use.mcp.client import MCPClient

from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.tools.views import HoverAction, ExtractionAction, FileExtractionAction, BrowserUseAgentExecution, \
    ReportWriterTask, TodoGenerateAction, TodoModifyAction, VibeSurfDoneAction
from vibe_surf.tools.mcp_client import CustomMCPClient
from vibe_surf.tools.file_system import CustomFileSystem
from vibe_surf.browser.browser_manager import BrowserManager

from vibe_surf.logger import get_logger

logger = get_logger(__name__)

Context = TypeVar('Context')

T = TypeVar('T', bound=BaseModel)


class VibeSurfTools:
    def __init__(self, exclude_actions: list[str] = [], mcp_server_config: Optional[Dict[str, Any]] = None):
        self.registry = Registry(exclude_actions)
        self._register_file_actions()
        self._register_browser_use_agent()
        self._register_report_writer_agent()
        self._register_todo_actions()
        self._register_done_action()
        self.mcp_server_config = mcp_server_config
        self.mcp_clients = {}

    def _register_browser_use_agent(self):
        @self.registry.action(
            'Execute browser_use agent tasks. Supports both single task execution (list length=1) and '
            'parallel execution of multiple tasks for improved efficiency. '
            'Accepts a list of tasks where each task can specify a tab_id (optional), '
            'task description (focusing on goals and expected returns), and task_files (optional). '
            'Browser_use agent has strong planning and execution capabilities, only needs task descriptions and desired outcomes.',
            param_model=BrowserUseAgentExecution,
        )
        async def execute_browser_use_agent(
                params: BrowserUseAgentExecution,
        ):
            """
            Execute browser_use agent tasks in parallel for improved efficiency.
            
            Args:
                params: BrowserUseAgentExecution containing list of tasks to execute
                browser_manager: Browser manager instance
                llm: Language model instance
                file_system: File system instance
                
            Returns:
                ActionResult with execution results
            """
            # TODO: Implement parallel execution of browser_use agent tasks
            # This is a placeholder implementation
            pass

    def _register_report_writer_agent(self):
        @self.registry.action(
            'Execute report writer agent to generate HTML reports. '
            'Task should describe report requirements, goals, insights observed, and any hints or tips for generating the report.',
            param_model=ReportWriterTask,
        )
        async def execute_report_writer_agent(
                params: ReportWriterTask,
        ):
            """
            Execute report writer agent to generate HTML reports.
            
            Args:
                params: ReportWriterTask containing task description with requirements and insights
                browser_manager: Browser manager instance
                llm: Language model instance
                file_system: File system instance
                
            Returns:
                ActionResult with generated report path
            """
            # TODO: Implement report writer agent execution
            # This is a placeholder implementation
            pass

    def _register_todo_actions(self):
        @self.registry.action(
            'Generate a new todo.md file with the provided todo items in markdown checkbox format.'
        )
        async def generate_todos(todo_items: list[str], file_system: CustomFileSystem):
            """Generate a new todo.md file with todo items in markdown format"""
            try:
                # Format todo items as markdown checkboxes
                formatted_items = []
                for item in todo_items:
                    # Clean item and ensure it doesn't already have checkbox format
                    clean_item = item.strip()
                    if clean_item.startswith('- ['):
                        formatted_items.append(clean_item)
                    else:
                        formatted_items.append(f'- [ ] {clean_item}')

                # Create content for todo.md
                content = '\n'.join(formatted_items) + '\n'

                # Write to todo.md file
                todo_path = file_system.get_dir() / 'todo.md'
                if todo_path.exists():
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    await file_system.move_file('todo.md', f'todos/todo-{timestamp}.md')
                result = await file_system.write_file('todo.md', content)

                logger.info(f'📝 Generated todo.md with {len(todo_items)} items')
                return ActionResult(
                    extracted_content=f'Todo file generated successfully with {len(todo_items)} items:\n{content}',
                    long_term_memory=f'Generated todo.md with {len(todo_items)} items',
                )

            except Exception as e:
                logger.error(f'❌ Failed to generate todo file: {e}')
                raise RuntimeError(f'Failed to generate todo file: {str(e)}')

        @self.registry.action(
            'Read the current todo.md file content.'
        )
        async def read_todos(file_system: CustomFileSystem):
            """Read the current todo.md file content"""
            try:
                # Read todo.md file
                result = await file_system.read_file('todo.md')

                logger.info(f'📖 Read todo.md file')
                return ActionResult(
                    extracted_content=result,
                    long_term_memory='Read current todo list',
                    include_in_memory=True,
                )

            except Exception as e:
                logger.error(f'❌ Failed to read todo file: {e}')
                return ActionResult(
                    extracted_content='Error: todo.md file not found or could not be read',
                    long_term_memory='Failed to read todo file',
                )

        @self.registry.action(
            'Modify existing todo items in todo.md file. Supports add, remove, complete, and uncomplete operations.',
            param_model=TodoModifyAction,
        )
        async def modify_todos(params: TodoModifyAction, file_system: CustomFileSystem):
            """Modify existing todo items using various operations"""
            try:
                # First read current content
                current_content = await file_system.read_file('todo.md')

                # Extract just the content part (remove the "Read from file..." prefix)
                if '<content>' in current_content and '</content>' in current_content:
                    start = current_content.find('<content>') + len('<content>')
                    end = current_content.find('</content>')
                    content = current_content[start:end].strip()
                else:
                    content = current_content.strip()

                modified_content = content
                changes_made = []

                # Process each modification
                for modification in params.modifications:
                    action = modification.action
                    item = modification.item.strip()

                    if action == 'add':
                        # Add new item
                        if item:
                            # Format as checkbox if not already formatted
                            if not item.startswith('- ['):
                                item = f'- [ ] {item}'
                            modified_content += f'\n{item}'
                            changes_made.append(f'Added: {item}')

                    elif action == 'remove':
                        # Remove item
                        if item:
                            # Try to find and remove the item (with some flexibility)
                            lines = modified_content.split('\n')
                            new_lines = []
                            removed = False
                            for line in lines:
                                if item in line or line.strip().endswith(item):
                                    removed = True
                                    changes_made.append(f'Removed: {line.strip()}')
                                else:
                                    new_lines.append(line)
                            modified_content = '\n'.join(new_lines)
                            if not removed:
                                changes_made.append(f'Item not found for removal: {item}')

                    elif action == 'complete':
                        # Mark item as complete: - [ ] → - [x]
                        if item:
                            lines = modified_content.split('\n')
                            completed = False
                            for i, line in enumerate(lines):
                                if item in line and '- [ ]' in line:
                                    lines[i] = line.replace('- [ ]', '- [x]')
                                    completed = True
                                    changes_made.append(f'Completed: {line.strip()} → {lines[i].strip()}')
                                    break
                            modified_content = '\n'.join(lines)
                            if not completed:
                                changes_made.append(f'Item not found for completion: {item}')

                    elif action == 'uncomplete':
                        # Mark item as uncomplete: - [x] → - [ ]
                        if item:
                            lines = modified_content.split('\n')
                            uncompleted = False
                            for i, line in enumerate(lines):
                                if item in line and '- [x]' in line:
                                    lines[i] = line.replace('- [x]', '- [ ]')
                                    uncompleted = True
                                    changes_made.append(f'Uncompleted: {line.strip()} → {lines[i].strip()}')
                                    break
                            modified_content = '\n'.join(lines)
                            if not uncompleted:
                                changes_made.append(f'Item not found for uncompletion: {item}')

                # If we made any add/remove/complete/uncomplete changes, write the updated content
                if any(change.startswith(('Added:', 'Removed:', 'Completed:', 'Uncompleted:')) for change in
                       changes_made):
                    await file_system.write_file('todo.md', modified_content + '\n')

                changes_summary = '\n'.join(changes_made) if changes_made else 'No changes made'

                logger.info(f'✏️ Modified todo.md: {len(changes_made)} changes')
                return ActionResult(
                    extracted_content=f'Todo modifications completed:\n{changes_summary}\n\nUpdated content:\n{modified_content}',
                    long_term_memory=f'Modified todo list: {len(changes_made)} changes made',
                )

            except Exception as e:
                logger.error(f'❌ Failed to modify todo file: {e}')
                raise RuntimeError(f'Failed to modify todo file: {str(e)}')

    def _register_done_action(self):
        @self.registry.action(
            'Complete task and output final response. Use for simple responses or comprehensive markdown summaries with optional follow-up task suggestions.',
            param_model=VibeSurfDoneAction,
        )
        async def task_done(
                params: VibeSurfDoneAction,
        ):
            """
            Complete task execution and provide final response.

            """
            pass

    def _register_file_actions(self):
        @self.registry.action(
            'Replace old_str with new_str in file_name. old_str must exactly match the string to replace in original text. Recommended tool to mark completed items in todo.md or change specific contents in a file.'
        )
        async def replace_file_str(file_name: str, old_str: str, new_str: str, file_system: FileSystem):
            result = await file_system.replace_file_str(file_name, old_str, new_str)
            logger.info(f'💾 {result}')
            return ActionResult(extracted_content=result, long_term_memory=result)

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
            'Extract content from a file. Support image files, pdf, markdown, txt, json, csv.',
            param_model=FileExtractionAction,
        )
        async def extract_content_from_file(
                params: FileExtractionAction,
                page_extraction_llm: BaseChatModel,
                file_system: CustomFileSystem,
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
            'Copy a file to the FileSystem. Set external_src=True to copy from external file(absolute path)to FileSystem, False to copy within FileSystem.'
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

        @self.registry.action(
            'List contents of a directory within the FileSystem. Use empty string "" or "." to list the root data_dir, or provide relative path for subdirectory.'
        )
        async def list_directory(directory_path: str, file_system: CustomFileSystem):
            result = await file_system.list_directory(directory_path)
            logger.info(f'📁 {result}')
            return ActionResult(
                extracted_content=result,
                include_in_memory=True,
                long_term_memory=result,
            )

        @self.registry.action(
            'Create a directory within the FileSystem.'
        )
        async def create_directory(directory_path: str, file_system: CustomFileSystem):
            result = await file_system.create_directory(directory_path)
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

    @time_execution_sync('--act')
    async def act(
            self,
            action: ActionModel,
            browser_manager: BrowserManager,
            llm: BaseChatModel | None = None,
            file_system: CustomFileSystem | None = None,
    ) -> ActionResult:
        """Execute an action"""

        for action_name, params in action.model_dump(exclude_unset=True).items():
            if params is not None:
                try:
                    if action_name not in self.registry.registry.actions:
                        raise ValueError(f'Action {action_name} not found')
                    action = self.registry.registry.actions[action_name]
                    special_context = {
                        'browser_manager': browser_manager,
                        'page_extraction_llm': llm,
                        'file_system': file_system,
                    }
                    try:
                        validated_params = action.param_model(**params)
                    except Exception as e:
                        raise ValueError(f'Invalid parameters {params} for action {action_name}: {type(e)}: {e}') from e

                    result = await action.function(params=validated_params, **special_context)
                except BrowserError as e:
                    logger.error(f'❌ Action {action_name} failed with BrowserError: {str(e)}')
                    result = handle_browser_error(e)
                except TimeoutError as e:
                    logger.error(f'❌ Action {action_name} failed with TimeoutError: {str(e)}')
                    result = ActionResult(error=f'{action_name} was not executed due to timeout.')
                except Exception as e:
                    # Log the original exception with traceback for observability
                    logger.error(f"Action '{action_name}' failed with error: {str(e)}")
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
