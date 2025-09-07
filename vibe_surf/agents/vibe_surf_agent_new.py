import asyncio
import json
import logging
import os
import pickle
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid_extensions import uuid7str
from json_repair import repair_json

from browser_use.browser.session import BrowserSession
from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import UserMessage, SystemMessage, BaseMessage, AssistantMessage, ContentPartTextParam, ContentPartImageParam, ImageURL
from browser_use.browser.views import TabInfo, BrowserStateSummary
from browser_use.filesystem.file_system import FileSystem
from pydantic import BaseModel, Field, ConfigDict, create_model

from vibe_surf.browser.browser_manager import BrowserManager
from vibe_surf.controller.vibesurf_tools import VibeSurfController
from vibe_surf.agents.browser_use_agent import BrowserUseAgent
from vibe_surf.agents.report_writer_agent import ReportWriterAgent
from vibe_surf.agents.prompts.vibe_surf_agent_new_prompt import (
    VIBE_SURF_AGENT_SYSTEM_PROMPT,
    PARALLEL_AGENT_EXECUTION_PROMPT,
    MANAGE_TODOS_PROMPT,
    GENERATE_REPORT_PROMPT,
    RESPONSE_PROMPT
)
from vibe_surf.logger import get_logger

logger = get_logger(__name__)


class AgentOutput(BaseModel):
    """Agent output model following browser_use patterns"""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra='forbid')
    
    thinking: str | None = None
    evaluation_previous_goal: str | None = None
    memory: str | None = None
    next_goal: str | None = None
    action: List[Any] = Field(
        ...,
        description='List of actions to execute',
        json_schema_extra={'min_items': 1},
    )
    
    @classmethod
    def model_json_schema(cls, **kwargs):
        schema = super().model_json_schema(**kwargs)
        schema['required'] = ['thinking', 'action']
        return schema
    
    @staticmethod
    def type_with_custom_actions(custom_actions: type) -> type:
        """Extend actions with custom actions"""
        model_ = create_model(
            'AgentOutput',
            __base__=AgentOutput,
            action=(
                list[custom_actions],  # type: ignore
                Field(..., description='List of actions to execute', json_schema_extra={'min_items': 1}),
            ),
            __module__=AgentOutput.__module__,
        )
        model_.__doc__ = 'AgentOutput model with custom actions'
        return model_


class VibeSurfAgent:
    """
    Simplified VibeSurf Agent without LangGraph dependency.
    
    Core workflow: get browser state -> LLM reasoning -> actions -> execution
    Supports parallel agent execution and reporting through registered actions.
    """
    
    def __init__(
        self,
        llm: BaseChatModel,
        browser_manager: BrowserManager,
        controller: VibeSurfController,
        workspace_dir: str = "./workspace",
    ):
        """Initialize simplified VibeSurf Agent"""
        self.llm = llm
        self.browser_manager = browser_manager
        self.controller = controller
        self.workspace_dir = workspace_dir
        
        # Ensure workspace directory exists
        os.makedirs(self.workspace_dir, exist_ok=True)
        
        # Session management
        self.cur_session_id: Optional[str] = None
        self.message_history: Dict[str, List[BaseMessage]] = {}
        self.activity_logs: Dict[str, List[Dict[str, str]]] = {}
        
        # Create file system for current workspace
        self.file_system = FileSystem(workspace_dir)
        
        # Register core actions with controller
        self._register_actions()
        
        # Setup dynamic action models from controller registry
        self._setup_action_models()
        
        logger.info("🌊 Simplified VibeSurf Agent initialized")

    def _setup_action_models(self):
        """Setup dynamic action models from controller registry"""
        # Create action model from controller registry
        self.ActionModel = self.controller.registry.create_action_model()
        # Create output model with the dynamic actions
        self.AgentOutput = AgentOutput.type_with_custom_actions(self.ActionModel)

    def _register_actions(self):
        """Register core actions with the controller using detailed prompts"""
        
        # Register parallel agent execution action
        @self.controller.registry.action(
            PARALLEL_AGENT_EXECUTION_PROMPT,
        )
        async def parallel_agent_execution(
            tasks: List[str],
        ):
            """Execute multiple browser_use_agent tasks in parallel for independent research and automation"""
            try:
                results = await self._execute_parallel_browser_use_agents(tasks)
                return {
                    "success": True,
                    "results": results,
                    "message": f"Executed {len(tasks)} parallel browser use agents successfully"
                }
            except Exception as e:
                logger.error(f"Parallel browser agent execution failed: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "message": "Parallel browser agent execution failed"
                }
        
        # Register report generation action
        @self.controller.registry.action(
            GENERATE_REPORT_PROMPT,
        )
        async def generate_report(
            original_task: str,
            execution_results: List[Dict],
            report_type: str = "detailed"
        ):
            """Generate comprehensive HTML report with professional formatting"""
            try:
                report_path = await self._generate_report(
                    original_task, execution_results, report_type
                )
                return {
                    "success": True,
                    "report_path": report_path,
                    "message": f"Professional HTML report generated at {report_path}"
                }
            except Exception as e:
                logger.error(f"Report generation failed: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "message": "Report generation failed"
                }
        
        # Register comprehensive todo management action using file system
        @self.controller.registry.action(
            MANAGE_TODOS_PROMPT,
        )
        async def manage_todos(
            operation: str,
            content: str = ""
        ):
            """Direct todo list management - LLM provides the content directly"""
            try:
                if operation == "create":
                    # Save LLM-provided todo content directly
                    await self.file_system.write_file("todo.md", content)
                    return {
                        "success": True,
                        "operation": "create",
                        "message": "Created todo list and saved to todo.md"
                    }
                elif operation == "read":
                    # Read current todo content
                    try:
                        todos = await self.file_system.read_file("todo.md")
                        return {
                            "success": True,
                            "todos": todos,
                            "operation": "read",
                            "message": "Retrieved current todo list"
                        }
                    except:
                        return {
                            "success": True,
                            "todos": "# Todo List\n\n(No todos yet)",
                            "operation": "read",
                            "message": "No todo list found"
                        }
                elif operation in ["update", "complete", "modify", "clean"]:
                    # Update with LLM-provided content directly
                    await self.file_system.write_file("todo.md", content)
                    return {
                        "success": True,
                        "operation": operation,
                        "message": f"Updated todo list and saved to todo.md"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Unknown operation: {operation}",
                        "message": "Supported operations: create, read, update, complete, modify, clean"
                    }
            except Exception as e:
                logger.error(f"Todo management failed: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "message": f"Todo management operation '{operation}' failed"
                }
        
        # Register response action for both simple responses and task completion
        @self.controller.registry.action(
            RESPONSE_PROMPT,
        )
        async def response(content: str):
            """Provide final response or task completion summary"""
            return {
                "success": True,
                "response": content,
                "message": "Response provided",
                "is_final": True
            }

    async def _get_browser_state_summary(self) -> BrowserStateSummary:
        """Get browser state summary similar to browser_use message manager"""
        try:
            main_session = self.browser_manager.main_browser_session
            
            # Get current page info
            current_url = await main_session.get_current_page_url()
            
            # Get page content and interactive elements
            # This would normally include the DOM elements with indexes
            page_content = await main_session.get_html_content()
            
            # Get screenshot if available
            screenshot = None
            try:
                screenshot_data = await main_session.take_screenshot()
                if screenshot_data:
                    screenshot = screenshot_data
            except Exception:
                pass
            
            # Get available tabs
            tabs = await main_session.get_tabs()
            
            # Create browser state summary similar to browser_use format
            browser_state = BrowserStateSummary(
                url=current_url or "about:blank",
                title="",  # Would extract from page
                content=page_content or "",
                screenshot=screenshot,
                tabs=tabs or []
            )
            
            return browser_state
            
        except Exception as e:
            logger.error(f"Failed to get browser state: {e}")
            # Return minimal state
            return BrowserStateSummary(
                url="about:blank",
                title="Error",
                content="Browser state unavailable",
                screenshot=None,
                tabs=[]
            )

    def _get_agent_state_description(self, task: str) -> str:
        """Get agent state description similar to browser_use format"""
        time_str = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        # Get todo contents if available
        todo_contents = self._get_todo_contents()
        if not todo_contents:
            todo_contents = '[Current todo.md is empty, fill it with your plan when applicable]'
        
        # Get file system description
        file_system_desc = self.file_system.describe() if self.file_system else 'No file system available'
        
        agent_state = f"""
<user_request>
{task}
</user_request>
<file_system>
{file_system_desc}
</file_system>
<todo_contents>
{todo_contents}
</todo_contents>
<step_info>
Current date and time: {time_str}
</step_info>
"""
        return agent_state

    def _get_todo_contents(self) -> str:
        """Get current todo contents for this session"""
        if not self.cur_session_id:
            return ""
        
        todo_file = os.path.join(
            self.workspace_dir, f"session_{self.cur_session_id}", "todo.md"
        )
        
        if os.path.exists(todo_file):
            try:
                with open(todo_file, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Failed to read todo file: {e}")
        
        return ""

    def _create_system_prompt(self) -> str:
        """Create system prompt for the agent"""
        return VIBE_SURF_AGENT_SYSTEM_PROMPT

    async def _execute_parallel_browser_use_agents(self, tasks: List[str]) -> List[Dict]:
        """Execute multiple browser_use_agent tasks in parallel"""
        logger.info(f"🔄 Executing {len(tasks)} parallel browser_use_agents")
        
        results = []
        agents = []
        
        try:
            # Create browser_use_agent for each task
            for i, task in enumerate(tasks):
                agent_id = f"agent-{i + 1}-{self.cur_session_id[-4:] if self.cur_session_id else 'temp'}"
                
                # Register agent with browser manager to get dedicated browser session
                browser_session = await self.browser_manager.register_agent(agent_id)
                
                # Create BrowserUseAgent with proper configuration
                task_id = f"{self.cur_session_id}-{i + 1}" if self.cur_session_id else f"temp-{i + 1}"
                file_system_path = os.path.join(self.workspace_dir, f"agent_{agent_id}")
                
                agent = BrowserUseAgent(
                    task=task,
                    llm=self.llm,
                    browser_session=browser_session,
                    controller=self.controller,
                    task_id=task_id,
                    file_system_path=file_system_path,
                    extend_system_message="You are working as part of a parallel execution. Focus on your specific task and provide clear, actionable results."
                )
                
                agents.append((agent, agent_id, task))
            
            # Execute all browser_use_agents in parallel
            agent_tasks = [agent[0].run() for agent in agents]
            histories = await asyncio.gather(*agent_tasks, return_exceptions=True)
            
            # Process results from browser_use_agents
            for i, ((agent, agent_id, task), history) in enumerate(zip(agents, histories)):
                if isinstance(history, Exception):
                    results.append({
                        "agent_id": agent_id,
                        "task": task,
                        "success": False,
                        "error": str(history)
                    })
                else:
                    # Extract results from browser_use_agent history
                    success = history.is_successful() if hasattr(history, 'is_successful') else True
                    result_text = history.final_result() if hasattr(history, 'final_result') else "Task completed"
                    error_text = str(history.errors()) if hasattr(history, 'errors') and history.has_errors() else None
                    
                    results.append({
                        "agent_id": agent_id,
                        "task": task,
                        "success": success,
                        "result": result_text,
                        "error": error_text
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Parallel browser_use_agent execution failed: {e}")
            raise
        finally:
            # Cleanup - unregister agents and close tabs
            for agent, agent_id, _ in agents:
                try:
                    await self.browser_manager.unregister_agent(agent_id, close_tabs=True)
                except Exception as e:
                    logger.warning(f"Failed to cleanup agent {agent_id}: {e}")

    async def _generate_report(
        self, 
        original_task: str, 
        execution_results: List[Dict], 
        report_type: str = "detailed"
    ) -> str:
        """Generate HTML report using ReportWriterAgent"""
        try:
            report_writer = ReportWriterAgent(
                llm=self.llm,
                workspace_dir=self.workspace_dir
            )
            
            report_data = {
                "original_task": original_task,
                "execution_results": execution_results,
                "report_type": report_type,
                "upload_files": []
            }
            
            report_path = await report_writer.generate_report(report_data)
            logger.info(f"📄 Report generated: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            raise


    def _save_session(self, session_id: str):
        """Save current session data to pickle files"""
        session_dir = os.path.join(self.workspace_dir, f"session_{session_id}")
        os.makedirs(session_dir, exist_ok=True)
        
        try:
            # Save message history
            if session_id in self.message_history:
                history_file = os.path.join(session_dir, "message_history.pkl")
                with open(history_file, 'wb') as f:
                    pickle.dump(self.message_history[session_id], f)
            
            # Save activity logs
            if session_id in self.activity_logs:
                logs_file = os.path.join(session_dir, "activity_logs.pkl")
                with open(logs_file, 'wb') as f:
                    pickle.dump(self.activity_logs[session_id], f)
            
            logger.info(f"💾 Session {session_id} saved")
            
        except Exception as e:
            logger.error(f"Failed to save session {session_id}: {e}")

    def _load_session(self, session_id: str):
        """Load session data from pickle files"""
        session_dir = os.path.join(self.workspace_dir, f"session_{session_id}")
        
        if not os.path.exists(session_dir):
            logger.info(f"📂 Creating new session {session_id}")
            self.message_history[session_id] = []
            self.activity_logs[session_id] = []
            return
        
        try:
            # Load message history
            history_file = os.path.join(session_dir, "message_history.pkl")
            if os.path.exists(history_file):
                with open(history_file, 'rb') as f:
                    self.message_history[session_id] = pickle.load(f)
            else:
                self.message_history[session_id] = []
            
            # Load activity logs
            logs_file = os.path.join(session_dir, "activity_logs.pkl")
            if os.path.exists(logs_file):
                with open(logs_file, 'rb') as f:
                    self.activity_logs[session_id] = pickle.load(f)
            else:
                self.activity_logs[session_id] = []
            
            logger.info(f"📂 Session {session_id} loaded")
            
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            # Initialize empty session on error
            self.message_history[session_id] = []
            self.activity_logs[session_id] = []

    def _switch_session(self, new_session_id: str):
        """Switch to a different session, saving current and loading new"""
        # Save current session if exists
        if self.cur_session_id:
            self._save_session(self.cur_session_id)
        
        # Load new session
        self.cur_session_id = new_session_id
        self._load_session(new_session_id)

    async def get_user_message(self, task: str, use_vision: bool = True) -> UserMessage:
        """Get complete state as a user message similar to browser_use pattern"""
        
        # Get browser state summary
        browser_state_summary = await self._get_browser_state_summary()
        
        # Build complete state description
        state_description = ""
        
        # Add agent state
        state_description += '<agent_state>\n' + self._get_agent_state_description(task).strip('\n') + '\n</agent_state>\n'
        
        # Add browser state with proper formatting
        state_description += f'<browser_state>\n'
        state_description += f'Current URL: {browser_state_summary.url}\n'
        if browser_state_summary.tabs:
            state_description += f'Open Tabs:\n'
            for i, tab in enumerate(browser_state_summary.tabs):
                state_description += f'[{i}] {tab.title} - {tab.url}\n'
        if browser_state_summary.content:
            # Add simplified content - in real implementation this would include interactive elements
            state_description += f'Page Content: {browser_state_summary.content[:500]}...\n'
        state_description += '</browser_state>\n'
        
        # Add read state if available
        read_state = self._get_read_state()
        if read_state:
            state_description += f'<read_state>\n{read_state}\n</read_state>\n'
        
        if use_vision and browser_state_summary.screenshot:
            # Create content parts with text and image
            content_parts: list[ContentPartTextParam | ContentPartImageParam] = [
                ContentPartTextParam(text=state_description)
            ]
            
            # Add screenshot
            content_parts.append(
                ContentPartImageParam(
                    image_url=ImageURL(
                        url=f'data:image/png;base64,{browser_state_summary.screenshot}',
                        media_type='image/png',
                        detail='high',
                    ),
                )
            )
            
            return UserMessage(content=content_parts, cache=True)
        else:
            return UserMessage(content=state_description, cache=True)

    def _get_read_state(self) -> str:
        """Get read state description for one-time information"""
        # This would contain information from previous actions that should be shown once
        # For now, return empty string
        return ""

    async def run(
        self,
        task: str,
        upload_files: Optional[List[str]] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """
        Main execution method for the simplified VibeSurf agent
        
        Args:
            task: User task to execute
            upload_files: Optional list of uploaded files
            session_id: Optional session ID for continuation
            
        Returns:
            str: Execution result in markdown format
        """
        logger.info(f"🚀 VibeSurf Agent starting task: {task[:100]}...")
        
        try:
            # Handle session management
            if session_id:
                if session_id != self.cur_session_id:
                    self._switch_session(session_id)
            else:
                # Create new session
                session_id = uuid7str()
                self._switch_session(session_id)
            
            # Initialize message history with system prompt if empty
            if not self.message_history[session_id]:
                self.message_history[session_id].append(
                    SystemMessage(content=self._create_system_prompt())
                )
            
            # Add user request to message history
            user_request = f"User's New Request: {task}"
            if upload_files:
                files_list = "\n".join([f"- {file}" for file in upload_files])
                user_request += f"\nUpload Files:\n{files_list}"
            
            self.message_history[session_id].append(
                UserMessage(content=user_request)
            )
            
            # Log user activity
            self.activity_logs[session_id].append({
                "agent_name": "user",
                "agent_status": "request",
                "agent_msg": user_request
            })
            
            # Main execution loop
            max_iterations = 10
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                logger.info(f"🔄 Iteration {iteration}")
                
                # Get current state and create user message
                user_message = await self.get_user_message(task)
                
                # Get current message history
                current_history = self.message_history[session_id].copy()
                current_history.append(user_message)
                
                # Get LLM response with structured output
                response = await self.llm.ainvoke(current_history, output_format=self.AgentOutput)
                model_output = response.completion
                
                # Handle empty actions with retry logic
                model_output = await self._get_model_output_with_retry(current_history, model_output)
                
                # Add response to message history
                self.message_history[session_id].append(
                    AssistantMessage(content=str(model_output.model_dump()))
                )
                
                # Log thinking
                if model_output.thinking:
                    self.activity_logs[session_id].append({
                        "agent_name": "vibesurf_agent",
                        "agent_status": "thinking",
                        "agent_msg": model_output.thinking
                    })
                
                # Execute actions
                action_results = await self._execute_actions(model_output.action)
                
                # Log action results
                for result in action_results:
                    self.activity_logs[session_id].append({
                        "agent_name": "vibesurf_agent",
                        "agent_status": "result" if result.get("success", False) else "error",
                        "agent_msg": result.get("message", "Action executed")
                    })
                
                # Check if task is complete
                if any(result.get("is_final", False) for result in action_results):
                    # Task is complete
                    final_result = next(
                        (result for result in action_results if result.get("is_final", False)),
                        {"response": "Task completed"}
                    )
                    
                    # Save session before returning
                    self._save_session(session_id)
                    
                    return f"# Task Completed\n\n{final_result.get('response', 'Task completed successfully.')}"
                
                # Continue to next iteration
                await asyncio.sleep(0.1)  # Small delay to prevent overwhelming
            
            # Max iterations reached
            self._save_session(session_id)
            return f"# Task Processing\n\nReached maximum iterations ({max_iterations}). Task may need manual intervention."
            
        except Exception as e:
            logger.error(f"❌ VibeSurf Agent execution failed: {e}")
            
            # Log error
            if session_id and session_id in self.activity_logs:
                self.activity_logs[session_id].append({
                    "agent_name": "vibesurf_agent",
                    "agent_status": "error",
                    "agent_msg": f"Execution failed: {str(e)}"
                })
                self._save_session(session_id)
            
            return f"# Task Execution Failed\n\n**Error:** {str(e)}\n\nPlease try again or contact support."

    async def _get_model_output_with_retry(self, input_messages: List[BaseMessage], model_output: AgentOutput) -> AgentOutput:
        """Get model output with retry logic for empty actions"""
        logger.debug(f'✅ Got LLM response with {len(model_output.action) if model_output.action else 0} actions')

        if (
            not model_output.action
            or not isinstance(model_output.action, list)
            or all(self._is_empty_action(action) for action in model_output.action)
        ):
            logger.warning('Model returned empty action. Retrying...')

            clarification_message = UserMessage(
                content='You forgot to return an action. Please respond with a valid JSON action according to the expected schema with your assessment and next actions.'
            )

            retry_messages = input_messages + [clarification_message]
            response = await self.llm.ainvoke(retry_messages, output_format=self.AgentOutput)
            model_output = response.completion

            if not model_output.action or all(self._is_empty_action(action) for action in model_output.action):
                logger.warning('Model still returned empty after retry. Inserting safe response action.')
                # Create a safe fallback action
                fallback_action = self.ActionModel()
                if hasattr(fallback_action, 'response'):
                    setattr(fallback_action, 'response', {
                        'content': 'No next action returned by LLM! Please try again.'
                    })
                else:
                    # If response action doesn't exist, create a basic action
                    setattr(fallback_action, 'done', {
                        'success': False,
                        'text': 'No next action returned by LLM!',
                    })
                model_output.action = [fallback_action]

        return model_output

    def _is_empty_action(self, action) -> bool:
        """Check if an action is empty"""
        try:
            if hasattr(action, 'model_dump'):
                return action.model_dump() == {}
            return action == {}
        except:
            return False

    async def multi_act(
        self,
        actions: List[Any],
        check_for_new_elements: bool = True
    ) -> List[Dict[str, Any]]:
        """Execute multiple actions, with parallel execution for allowed action types"""
        results: List[Dict[str, Any]] = []
        total_actions = len(actions)
        
        if not actions:
            return results
        
        try:
            # Group actions for potential parallel execution
            action_groups = self._group_actions_for_parallel_execution(actions)
            
            # Track global action index for logging
            global_action_index = 0
            
            for group_index, action_group in enumerate(action_groups):
                group_size = len(action_group)
                
                # Check if this group can be executed in parallel
                can_execute_in_parallel = (
                    group_size > 1 and
                    all(self._is_action_parallel_allowed(action) for action in action_group)
                )
                
                if can_execute_in_parallel:
                    logger.info(f'🚀 Executing {group_size} actions in parallel: group {group_index + 1}/{len(action_groups)}')
                    # Execute actions in parallel using asyncio.gather
                    parallel_results = await self._execute_actions_in_parallel(
                        action_group, global_action_index, total_actions
                    )
                    results.extend(parallel_results)
                    global_action_index += group_size
                    
                    # Check if any result indicates completion or error
                    if any(result.get("is_final", False) or result.get("error") for result in parallel_results):
                        break
                else:
                    # Execute actions sequentially
                    for local_index, action in enumerate(action_group):
                        i = global_action_index + local_index
                        
                        # wait between actions (only after first action)
                        if i > 0:
                            await asyncio.sleep(0.1)  # Small delay between actions
                        
                        # Execute single action
                        try:
                            action_result = await self._execute_single_action(action, i, total_actions)
                            results.append(action_result)
                            
                            if action_result.get("is_final", False) or action_result.get("error") or i == total_actions - 1:
                                break
                                
                        except Exception as e:
                            logger.error(f'❌ Executing action {i + 1} failed: {type(e).__name__}: {e}')
                            results.append({
                                "success": False,
                                "error": str(e),
                                "message": f"Action execution failed: {str(e)}"
                            })
                            break
                    
                    global_action_index += len(action_group)
            
            return results
            
        except Exception as e:
            logger.error(f"Multi-action execution failed: {e}")
            return [{
                "success": False,
                "error": str(e),
                "message": f"Multi-action execution failed: {str(e)}"
            }]

    async def _execute_actions_in_parallel(
        self,
        actions: List[Any],
        start_index: int,
        total_actions: int
    ) -> List[Dict[str, Any]]:
        """Execute a group of actions in parallel using asyncio.gather"""
        
        async def execute_single_parallel_action(action: Any, action_index: int) -> Dict[str, Any]:
            """Execute a single action for parallel execution"""
            
            # Get action info for logging
            action_name = "unknown"
            action_params = ""
            
            if hasattr(action, 'model_dump'):
                action_data = action.model_dump(exclude_unset=True)
                action_name = next(iter(action_data.keys())) if action_data else 'unknown'
                action_params = str(action_data.get(action_name, ''))[:140]
            
            time_start = time.time()
            blue = '\033[34m'
            reset = '\033[0m'
            logger.info(f'  🦾 {blue}[PARALLEL ACTION {action_index + 1}/{total_actions}]{reset} {action_params}')
            
            # Execute the action
            result = await self._execute_single_action(action, action_index, total_actions)
            
            time_end = time.time()
            time_elapsed = time_end - time_start
            
            green = '\033[92m'
            logger.debug(
                f'☑️ Parallel action {action_index + 1}/{total_actions}: {green}{action_params}{reset} in {time_elapsed:.2f}s'
            )
            
            return result
        
        # Create tasks for parallel execution
        tasks = [
            execute_single_parallel_action(action, start_index + i)
            for i, action in enumerate(actions)
        ]
        
        # Execute all tasks in parallel
        parallel_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and handle any exceptions
        processed_results = []
        for i, result in enumerate(parallel_results):
            if isinstance(result, Exception):
                action_index = start_index + i
                logger.error(f'❌ Parallel action {action_index + 1} failed: {type(result).__name__}: {result}')
                processed_results.append({
                    "success": False,
                    "error": str(result),
                    "message": f"Parallel action execution failed: {str(result)}"
                })
            else:
                processed_results.append(result)
        
        return processed_results

    async def _execute_single_action(self, action: Any, action_index: int, total_actions: int) -> Dict[str, Any]:
        """Execute a single action and return result"""
        try:
            # Convert action model to dict if needed
            if hasattr(action, 'model_dump'):
                action_dict = action.model_dump()
            else:
                action_dict = action
            
            # Get action name and parameters - find the first non-None field
            action_name = None
            action_params = {}
            
            for field_name, field_value in action_dict.items():
                if field_value is not None:
                    action_name = field_name
                    action_params = field_value if isinstance(field_value, dict) else {'value': field_value}
                    break
            
            if not action_name:
                return {
                    "success": False,
                    "error": "No valid action found",
                    "message": "Action object has no valid fields"
                }
            
            logger.info(f"🎯 Executing action {action_index + 1}/{total_actions}: {action_name}")
            
            # Execute action through controller if registered
            if hasattr(self.controller.registry, 'registry') and \
               hasattr(self.controller.registry.registry, 'actions') and \
               action_name in self.controller.registry.registry.actions:
                
                # Action is registered with controller
                action_func = self.controller.registry.registry.actions[action_name]
                result = await action_func(**action_params)
                
            else:
                # Handle built-in actions
                if action_name == "response":
                    result = {
                        "success": True,
                        "response": action_params.get("content", ""),
                        "message": "Response provided",
                        "is_final": True
                    }
                else:
                    # Unknown action
                    result = {
                        "success": False,
                        "error": f"Unknown action: {action_name}",
                        "message": f"Action {action_name} not recognized"
                    }
            
            return result
            
        except Exception as e:
            logger.error(f"Single action execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Single action execution failed: {str(e)}"
            }

    def _group_actions_for_parallel_execution(self, actions: List[Any]) -> List[List[Any]]:
        """Group actions for potential parallel execution"""
        groups = []
        current_group = []
        
        for action in actions:
            action_name = self._get_action_name(action)
            
            # Start new group if current action cannot be parallelized with previous ones
            if current_group and not self._can_parallelize_with_group(action, current_group):
                groups.append(current_group)
                current_group = [action]
            else:
                current_group.append(action)
        
        if current_group:
            groups.append(current_group)
        
        return groups

    def _is_action_parallel_allowed(self, action: Any) -> bool:
        """Check if an action can be executed in parallel"""
        action_name = self._get_action_name(action)
        
        # Define which actions can be executed in parallel
        parallel_allowed_actions = {
            'parallel_agent_execution',
            'generate_report',
            'manage_todos',
            'response'
        }
        
        return action_name in parallel_allowed_actions

    def _can_parallelize_with_group(self, action: Any, group: List[Any]) -> bool:
        """Check if an action can be parallelized with a group of actions"""
        action_name = self._get_action_name(action)
        
        # Check if all actions in the group can be parallelized
        if not self._is_action_parallel_allowed(action):
            return False
        
        for group_action in group:
            if not self._is_action_parallel_allowed(group_action):
                return False
        
        return True

    def _get_action_name(self, action: Any) -> str:
        """Get action name from action object"""
        if hasattr(action, 'model_dump'):
            action_dict = action.model_dump(exclude_unset=True)
            return next(iter(action_dict.keys())) if action_dict else 'unknown'
        elif isinstance(action, dict):
            return next(iter(action.keys())) if action else 'unknown'
        return 'unknown'

    async def _execute_actions(self, actions: List[Any]) -> List[Dict[str, Any]]:
        """Execute a list of actions using the multi_act method"""
        return await self.multi_act(actions, check_for_new_elements=True)

    def get_activity_logs(
        self, 
        session_id: Optional[str] = None, 
        message_index: Optional[int] = None
    ) -> Optional[Union[List[Dict], Dict]]:
        """Get activity logs for a specific session"""
        session_id = session_id or self.cur_session_id
        
        if not session_id or session_id not in self.activity_logs:
            return None
        
        session_logs = self.activity_logs[session_id]
        
        if message_index is None:
            return session_logs
        else:
            if message_index < len(session_logs):
                return session_logs[message_index]
            return None

    def get_current_session_id(self) -> Optional[str]:
        """Get current session ID"""
        return self.cur_session_id