import asyncio
import copy
import json
import logging
import os
import pdb
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import pickle
import nanoid
import shutil
from typing import Any, Dict, List, Literal, Optional
from uuid_extensions import uuid7str
from collections import defaultdict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field
from json_repair import repair_json

from browser_use.browser.session import BrowserSession
from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import UserMessage, SystemMessage, BaseMessage, AssistantMessage
from browser_use.browser.views import TabInfo
from browser_use.tokens.service import TokenCost

from vibe_surf.agents.browser_use_agent import BrowserUseAgent
from vibe_surf.agents.report_writer_agent import ReportWriterAgent, ReportTaskResult
from vibe_surf.agents.views import CustomAgentOutput
from vibe_surf.utils import check_latest_vibesurf_version, get_vibesurf_version

from vibe_surf.agents.prompts.vibe_surf_prompt import (
    VIBESURF_SYSTEM_PROMPT,
    EXTEND_BU_SYSTEM_PROMPT
)
from vibe_surf.browser.browser_manager import BrowserManager
from vibe_surf.tools.browser_use_tools import BrowserUseTools
from vibe_surf.tools.vibesurf_tools import VibeSurfTools
from vibe_surf.tools.file_system import CustomFileSystem
from vibe_surf.agents.views import VibeSurfAgentSettings

from vibe_surf.telemetry.service import ProductTelemetry
from vibe_surf.telemetry.views import (
    VibeSurfAgentTelemetryEvent,
    VibeSurfAgentParsedOutputEvent,
    VibeSurfAgentExceptionEvent
)

from vibe_surf.logger import get_logger

logger = get_logger(__name__)


class BrowserTaskResult(BaseModel):
    """Result from browser task execution"""
    agent_id: str
    agent_workdir: str
    success: bool
    task: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    important_files: Optional[List[str]] = None


class ControlResult(BaseModel):
    """Result of a control operation"""
    success: bool
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)
    details: Optional[Dict[str, Any]] = None


class AgentStatus(BaseModel):
    """Status of an individual agent"""
    agent_id: str
    status: Literal["running", "paused", "stopped", "idle", "error"] = "idle"
    current_action: Optional[str] = None
    last_update: datetime = Field(default_factory=datetime.now)
    error_message: Optional[str] = None
    pause_reason: Optional[str] = None


class VibeSurfStatus(BaseModel):
    """Overall status of the vibesurf execution"""
    overall_status: Literal["running", "paused", "stopped", "idle", "error"] = "idle"
    agent_statuses: Dict[str, AgentStatus] = Field(default_factory=dict)
    progress: Dict[str, Any] = Field(default_factory=dict)
    last_update: datetime = Field(default_factory=datetime.now)
    active_step: Optional[str] = None


@dataclass
class VibeSurfState:
    """LangGraph state for VibeSurfAgent workflow"""

    # Core task information
    original_task: str = ""
    upload_files: List[str] = field(default_factory=list)
    session_id: str = field(default_factory=lambda: uuid7str())
    current_workspace_dir: str = "./workspace"

    # Workflow state
    current_step: str = "vibesurf_agent"
    is_complete: bool = False

    # Current action and parameters from LLM
    current_action: Optional[str] = None
    action_params: Optional[Dict[str, Any]] = None

    # Browser task execution
    browser_tasks: List[Dict[str, Any]] = field(default_factory=list)
    browser_results: List[BrowserTaskResult] = field(default_factory=list)

    generated_report_result: Optional[ReportTaskResult] = None
    
    # Response outputs
    final_response: Optional[str] = None

    # vibesurf_agent
    vibesurf_agent: Optional['VibeSurfAgent'] = None

    # Control state management
    paused: bool = False
    stopped: bool = False
    should_pause: bool = False
    should_stop: bool = False


def format_browser_results(browser_results: List[BrowserTaskResult]) -> str:
    """Format browser results for LLM prompt"""
    result_text = []
    for result in browser_results:
        status = "✅ Success" if result.success else "❌ Failed"
        result_text.append(f"{status}: {result.task}")
        if result.result:
            result_text.append(f"  Result: {result.result}...")
        if result.error:
            result_text.append(f"  Error: {result.error}")
    return "\n".join(result_text)


def process_agent_msg_file_links(agent_msg: str, agent_name: str, base_dir: Path) -> str:
    """
    Process file links in agent_msg, converting relative paths to absolute paths
    
    Args:
        agent_msg: The agent message containing potential file links
        agent_name: Name of the agent (used for special handling of browser_use_agent)
        base_dir: Base directory path from file_system.get_dir()
    
    Returns:
        Processed agent_msg with absolute paths
    """
    # Pattern to match markdown links: [text](path)
    link_pattern = r'\[([^\]]*)\]\(([^)]+)\)'
    
    def replace_link(match):
        text = match.group(1)
        path = match.group(2)
        
        # Skip if already an absolute path or URL
        if path.startswith(('http://', 'https://', 'file:///', '/')):
            return match.group(0)
        
        # Build absolute path
        if agent_name.startswith('browser_use_agent-'):
            # Extract task_id and index from agent_name
            # Format: browser_use_agent-{task_id}-{i + 1:03d}
            parts = agent_name.split('-')
            if len(parts) >= 3:
                task_id = parts[1]
                index = parts[2]
                # Add the special sub-path for browser_use_agent
                sub_path = f"bu_agents/{task_id}-{index}"
                absolute_path = base_dir / sub_path / path
            else:
                absolute_path = base_dir / path
        else:
            absolute_path = base_dir / path
        
        # Convert to string and normalize separators
        abs_path_str = str(absolute_path).replace(os.path.sep, '/')
        
        return f"[{text}](file:///{abs_path_str})"
    
    # Replace all file links
    processed_msg = re.sub(link_pattern, replace_link, agent_msg)
    return processed_msg


async def log_agent_activity(state: VibeSurfState, agent_name: str, agent_status: str, agent_msg: str) -> None:
    """Log agent activity to the activity log"""
    token_summary = await state.vibesurf_agent.token_cost_service.get_usage_summary()
    token_summary_md = token_summary.model_dump_json(indent=2, exclude_none=True, exclude_unset=True)
    logger.debug(token_summary_md)

    # Process file links in agent_msg to convert relative paths to absolute paths
    base_dir = state.vibesurf_agent.file_system.get_dir()
    processed_agent_msg = process_agent_msg_file_links(agent_msg, agent_name, base_dir)

    activity_entry = {
        "agent_name": agent_name,
        "agent_status": agent_status,  # working, result, error
        "agent_msg": processed_agent_msg,
        "timestamp": datetime.now().isoformat(),
        "total_tokens": token_summary.total_tokens,
        "total_cost": token_summary.total_cost
    }
    state.vibesurf_agent.activity_logs.append(activity_entry)
    logger.debug(f"📝 Logged activity: {agent_name} - {agent_status}:\n{processed_agent_msg}")


def create_browser_agent_step_callback(state: VibeSurfState, agent_name: str):
    """Create a step callback function for browser-use agent to log each step"""

    async def step_callback(browser_state_summary, agent_output, step_num: int) -> None:
        """Callback function to log browser agent step information"""
        try:
            # Format step information as markdown
            step_msg = f"## Step {step_num}\n\n"

            # Add thinking if present
            if hasattr(agent_output, 'thinking') and agent_output.thinking:
                step_msg += f"**💡 Thinking:**\n{agent_output.thinking}\n\n"

            # Add evaluation if present
            if hasattr(agent_output, 'evaluation_previous_goal') and agent_output.evaluation_previous_goal:
                step_msg += f"**👍 Evaluation:**\n{agent_output.evaluation_previous_goal}\n\n"

            # Add memory if present
            # if agent_output.memory:
            #     step_msg += f"**🧠 Memory:** {agent_output.memory}\n\n"

            # Add next goal if present
            if hasattr(agent_output, 'next_goal') and agent_output.next_goal:
                step_msg += f"**🎯 Next Goal:**\n{agent_output.next_goal}\n\n"

            # Add action summary
            if agent_output.action and len(agent_output.action) > 0:
                action_count = len(agent_output.action)
                step_msg += f"**⚡ Actions:**\n"

                all_action_data = []
                # Add brief action details
                for i, action in enumerate(agent_output.action):
                    action_data = action.model_dump(exclude_unset=True, exclude_none=True)
                    all_action_data.append(action_data)
                step_msg += f"```json\n{json.dumps(all_action_data, indent=2, ensure_ascii=False)}\n```"
            else:
                step_msg += f"**⚡ Actions:** No actions\n"

            # Log the step activity
            await log_agent_activity(state, agent_name, "working", step_msg.strip())

        except Exception as e:
            logger.error(f"❌ Error in step callback for {agent_name}: {e}")
            # Log a simple fallback message
            await log_agent_activity(state, agent_name, "step", f"Step {step_num} completed")

    return step_callback


def create_report_writer_step_callback(state: VibeSurfState, agent_name: str):
    """Create a step callback function for report writer agent to log each step"""

    async def step_callback(parsed_output, step_num: int) -> None:
        """Callback function to log report writer agent step information"""
        try:
            # Format step information as markdown
            step_msg = f"## Step {step_num}\n\n"

            # Add thinking if present
            if hasattr(parsed_output, 'thinking') and parsed_output.thinking:
                step_msg += f"**💡 Thinking:**\n{parsed_output.thinking}\n\n"

            # Add action summary
            if hasattr(parsed_output, 'action') and parsed_output.action:
                step_msg += f"**⚡ Actions:**\n"

                # Add brief action details
                action = parsed_output.action
                action_data = action.model_dump(exclude_unset=True, exclude_none=True)
                step_msg += f"```json\n{json.dumps(action_data, indent=2, ensure_ascii=False)}\n```"
            else:
                step_msg += f"**⚡ Actions:** No actions\n"

            # Log the step activity
            await log_agent_activity(state, agent_name, "working", step_msg.strip())

        except Exception as e:
            logger.error(f"❌ Error in step callback for {agent_name}: {e}")
            # Log a simple fallback message
            await log_agent_activity(state, agent_name, "step", f"Step {step_num} completed")

    return step_callback


# Control-aware node wrapper
async def control_aware_node(node_func, state: VibeSurfState, node_name: str) -> VibeSurfState:
    """
    Wrapper for workflow nodes that adds control state checking
    """
    # Check control state before executing node
    if state.stopped:
        logger.info(f"🛑 Node {node_name} skipped - workflow stopped")
        return state

    # Handle pause state
    while state.paused or state.should_pause:
        if not state.paused and state.should_pause:
            logger.info(f"⏸️ Node {node_name} pausing workflow")
            state.paused = True
            state.should_pause = False

        logger.debug(f"⏸️ Node {node_name} waiting - workflow paused")
        await asyncio.sleep(0.5)  # Check every 500ms

        # Allow stopping while paused
        if state.stopped or state.should_stop:
            logger.info(f"🛑 Node {node_name} stopped while paused")
            state.stopped = True
            state.should_stop = False
            return state

    # Check for stop signal
    if state.should_stop:
        logger.info(f"🛑 Node {node_name} stopping workflow")
        state.stopped = True
        state.should_stop = False
        return state

    # Execute the actual node
    logger.debug(f"▶️ Executing node: {node_name}")

    try:
        return await node_func(state)
    except Exception as e:
        logger.error(f"❌ Node {node_name} failed: {e}")
        raise


# LangGraph Nodes

async def vibesurf_agent_node(state: VibeSurfState) -> VibeSurfState:
    """
    Main VibeSurf agent node using thinking + action pattern like report_writer_agent
    """
    return await control_aware_node(_vibesurf_agent_node_impl, state, "vibesurf_agent")


async def _vibesurf_agent_node_impl(state: VibeSurfState) -> VibeSurfState:
    """Implementation using thinking + action pattern similar to report_writer_agent"""

    agent_name = "vibesurf_agent"

    # Create action model and agent output using VibeSurfTools
    vibesurf_agent = state.vibesurf_agent

    vibesurf_action_names = vibesurf_agent.tools.get_all_action_names(exclude_actions=['mcp.', 'cpo.'])
    ActionModel = vibesurf_agent.tools.registry.create_action_model(include_actions=vibesurf_action_names)
    if vibesurf_agent.settings.agent_mode == "thinking":
        AgentOutput = CustomAgentOutput.type_with_custom_actions(ActionModel)
    else:
        AgentOutput = CustomAgentOutput.type_with_custom_actions_no_thinking(ActionModel)

    # Get current browser context
    browser_tabs = await vibesurf_agent.browser_manager.main_browser_session.get_tabs()
    active_browser_tab = await vibesurf_agent.browser_manager.get_activate_tab()

    # Format context information
    context_info = []
    context_info.append(f"Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if browser_tabs:
        browser_tabs_info = {}
        for tab in browser_tabs:
            browser_tabs_info[tab.target_id[-4:]] = {
                "page_title": tab.title,
                "page_url": tab.url,
            }
        context_info.append(
            f"Current Available Browser Tabs:\n{json.dumps(browser_tabs_info, ensure_ascii=False, indent=2)}\n")
    if active_browser_tab:
        context_info.append(f"Current Active Browser Tab:{active_browser_tab.target_id[-4:]}\n")
    if state.browser_results:
        results_md = format_browser_results(state.browser_results)
        context_info.append(f"Previous Browser Results:\n{results_md}\n")
    if state.generated_report_result:
        if state.generated_report_result.success:
            context_info.append(f"Generated Report: ✅ Success - {state.generated_report_result.report_path}\n")
        else:
            context_info.append(f"Generated Report: ❌ Failed - {state.generated_report_result.msg}\nPath: {state.generated_report_result.report_path}\n")

    context_str = "\n".join(context_info) if context_info else "No additional context available."
    logger.debug("VibeSurf State Message:\n")
    logger.debug(context_str)
    vibesurf_agent.message_history.append(UserMessage(content=context_str))

    try:
        # Get LLM response with action output format
        response = await vibesurf_agent.llm.ainvoke(vibesurf_agent.message_history, output_format=AgentOutput)
        parsed = response.completion
        action = parsed.action
        vibesurf_agent.message_history.append(
            AssistantMessage(content=json.dumps(response.completion.model_dump(exclude_none=True, exclude_unset=True),
                                                ensure_ascii=False)))

        # Capture telemetry for parsed output
        import vibe_surf
        action_types = []
        action_data = action.model_dump(exclude_unset=True)
        action_name = next(iter(action_data.keys())) if action_data else 'unknown'
        action_types.append(action_name)
        
        parsed_output_event = VibeSurfAgentParsedOutputEvent(
            version=vibe_surf.__version__,
            parsed_output=json.dumps(parsed.model_dump(exclude_none=True, exclude_unset=True), ensure_ascii=False),  # Limit size
            action_count=1,
            action_types=action_types,
            model=getattr(vibesurf_agent.llm, 'model_name', None),
            session_id=state.session_id,
        )
        vibesurf_agent.telemetry.capture(parsed_output_event)
        vibesurf_agent.telemetry.flush()

        # Log thinking if present
        if hasattr(parsed, 'thinking') and parsed.thinking:
            await log_agent_activity(state, agent_name, "thinking", parsed.thinking)
        action_data = action.model_dump(exclude_unset=True)
        action_name = next(iter(action_data.keys())) if action_data else 'unknown'
        logger.info(f"🛠️ Processing VibeSurf action: {action_name}")

        # Check for special routing actions
        if action_name == 'execute_browser_use_agent':
            # Route to browser task execution node
            params = action_data[action_name]
            state.browser_tasks = params.get('tasks', [])
            state.current_action = 'execute_browser_use_agent'
            state.action_params = params
            state.current_step = "browser_task_execution"

            # Log agent activity
            browser_tasks_md = []
            for browser_task in state.browser_tasks:
                bu_task = browser_task.get('task', "")
                if bu_task:
                    bu_task_tabid = browser_task.get('tab_id', "")
                    browser_tasks_md.append(f"- [ ] Tab id: {bu_task_tabid} working {bu_task}")
            browser_tasks_md = '\n'.join(browser_tasks_md)
            agent_msg = f"Routing to browser task execution with  {len(state.browser_tasks)} browser tasks:\n\n{browser_tasks_md}"
            await log_agent_activity(state, agent_name, "working", agent_msg)
            logger.debug(agent_msg)
            return state

        elif action_name == 'execute_report_writer_agent':
            # Route to report task execution node
            params = action_data[action_name]
            state.current_action = 'execute_report_writer_agent'
            state.action_params = params
            state.current_step = "report_task_execution"
            report_task = params.get('task', "")
            agent_msg = f"Routing to report generation with task:\n{report_task}"
            await log_agent_activity(state, agent_name, "working", agent_msg)
            return state

        elif action_name == 'task_done':
            # Handle response/completion - direct to END
            params = action_data[action_name]
            response_content = params.get('response', 'Task completed!')
            follow_tasks = params.get('suggestion_follow_tasks', [])
            state.current_step = "END"

            # Format final response
            final_response = f"{response_content}"
            await log_agent_activity(state, agent_name, "result", final_response)

            if follow_tasks:
                await log_agent_activity(state, agent_name, "suggestion_tasks",
                                         '\n'.join(follow_tasks))
                final_response += "\n\n## Suggested Follow-up Tasks:\n"
                for j, task in enumerate(follow_tasks[:3], 1):
                    final_response += f"{j}. {task}\n"

            state.final_response = final_response
            logger.debug(final_response)
            state.is_complete = True
            return state

        else:
            if "todos" in action_name:
                todo_content = await vibesurf_agent.file_system.read_file('todo.md')
                action_msg = f"{action_name}:\n\n{todo_content}"
                logger.debug(action_msg)
                await log_agent_activity(state, agent_name, "working", action_msg)
            else:
                action_msg = f"**⚡ Actions:**\n"
                action_msg += f"```json\n{json.dumps(action_data, indent=2, ensure_ascii=False)}\n```"
                logger.debug(action_msg)
                await log_agent_activity(state, agent_name, "working", action_msg)

            result = await vibesurf_agent.tools.act(
                action=action,
                browser_manager=vibesurf_agent.browser_manager,
                llm=vibesurf_agent.llm,
                file_system=vibesurf_agent.file_system,
            )

            state.current_step = "vibesurf_agent"

            if result.extracted_content:
                vibesurf_agent.message_history.append(
                    UserMessage(content=f'Action result:\n{result.extracted_content}'))
                await log_agent_activity(state, agent_name, "result", result.extracted_content)

            if result.error:
                vibesurf_agent.message_history.append(UserMessage(content=f'Action error:\n{result.error}'))
                await log_agent_activity(state, agent_name, "error", result.error)

        return state

    except Exception as e:
        import traceback
        traceback_str = traceback.format_exc()
        traceback.print_exc()
        logger.error(f"❌ VibeSurf agent failed: {e}")
        
        # Capture telemetry for exception
        import vibe_surf
        exception_event = VibeSurfAgentExceptionEvent(
            version=vibe_surf.__version__,
            error_message=str(e)[:500],  # Limit error message length
            error_type=type(e).__name__,
            traceback=traceback_str[:1000],  # Limit traceback length
            model=getattr(vibesurf_agent.llm, 'model_name', None),
            session_id=state.session_id,
            function_name='_vibesurf_agent_node_impl'
        )
        vibesurf_agent.telemetry.capture(exception_event)
        vibesurf_agent.telemetry.flush()

        state.final_response = f"Task execution failed: {str(e)}"
        state.is_complete = True
        await log_agent_activity(state, agent_name, "error", f"Agent failed: {str(e)}")
        return state


async def browser_task_execution_node(state: VibeSurfState) -> VibeSurfState:
    """
    Execute browser tasks assigned by supervisor agent
    """
    return await control_aware_node(_browser_task_execution_node_impl, state, "browser_task_execution")


async def _browser_task_execution_node_impl(state: VibeSurfState) -> VibeSurfState:
    """Implementation of browser task execution node - simplified tab-based approach"""
    logger.info("🚀 Executing browser tasks assigned by vibesurf agent...")
    try:
        task_count = len(state.browser_tasks)
        if task_count == 0:
            raise ValueError("No browser tasks assigned. Please assign 1 task at least.")
        if not state.browser_results:
            state.browser_results = []
        if task_count <= 1:
            # Single task execution
            logger.info("📝 Using single execution for single task")
            result = await execute_single_browser_tasks(state)
            results = [result]
            # Update browser results
            state.browser_results.extend(results)
        else:
            # Multiple tasks execution - parallel approach
            logger.info(f"🚀 Using parallel execution for {task_count} tasks")
            results = await execute_parallel_browser_tasks(state)
            # Update browser results
            state.browser_results.extend(results)

        # Return to vibesurf agent for next decision
        state.current_step = "vibesurf_agent"

        # Log result
        successful_tasks = sum(1 for result in results if result.success)
        await log_agent_activity(state, "browser_task_executor", "result",
                                 f"Browser execution completed: {successful_tasks}/{len(results)} tasks successful")

        logger.info(f"✅ Browser task execution completed with {len(results)} results")
        return state

    except Exception as e:
        logger.error(f"❌ Browser task execution failed: {e}")
        import traceback
        traceback.print_exc()
        state.browser_results.append(BrowserTaskResult(
            agent_id="unknown",
            agent_workdir="unknown",
            task='unknown',
            success=False,
            error=str(e)
        )
        )
        state.current_step = "vibesurf_agent"

        await log_agent_activity(state, "browser_task_executor", "error", f"Browser execution failed: {str(e)}")
        return state


async def execute_parallel_browser_tasks(state: VibeSurfState) -> List[BrowserTaskResult] | None:
    """Execute pending tasks in parallel using multiple browser agents"""
    logger.info("🔄 Executing pending tasks in parallel...")

    # Register agents with browser manager
    agents = []
    pending_tasks = state.browser_tasks
    bu_agent_ids = []
    register_sessions = []
    task_id = nanoid.generate(size=5)
    bu_agents_workdir = state.vibesurf_agent.file_system.get_dir() / "bu_agents"
    bu_agents_workdir.mkdir(parents=True, exist_ok=True)

    for i, task_info in enumerate(pending_tasks):
        agent_id = f"bu_agent-{task_id}-{i + 1:03d}"
        task_description = task_info.get('task', '')
        if not task_description:
            continue
        target_id = task_info.get('tab_id', None)
        register_sessions.append(
            state.vibesurf_agent.browser_manager.register_agent(agent_id, target_id=target_id)
        )
        bu_agent_ids.append(agent_id)
    agent_browser_sessions = await asyncio.gather(*register_sessions)

    vibesurf_tools = state.vibesurf_agent.tools
    bu_tools = BrowserUseTools()
    # for mcp_server_name, mcp_client in vibesurf_tools.mcp_clients.items():
    #     await mcp_client.register_to_tools(
    #         tools=bu_tools,
    #         prefix=f"mcp.{mcp_server_name}."
    #     )
    bu_tasks = [None] * len(pending_tasks)
    for i, task_info in enumerate(pending_tasks):
        agent_id = f"bu_agent-{task_id}-{i + 1:03d}"
        task_description = task_info.get('task', '')
        if not task_description:
            continue
        task_files = task_info.get('task_files', [])
        bu_agent_workdir = bu_agents_workdir / f"{task_id}-{i + 1:03d}"
        bu_agent_workdir.mkdir(parents=True, exist_ok=True)
        agent_name = f"browser_use_agent-{task_id}-{i + 1:03d}"
        # Log agent creation
        await log_agent_activity(state, agent_name, "working", f"{task_description}")

        try:
            available_file_paths = []
            if task_files:
                for task_file in task_files:
                    upload_workdir = bu_agent_workdir / "upload_files"
                    upload_workdir.mkdir(parents=True, exist_ok=True)
                    task_file_path = state.vibesurf_agent.file_system.get_absolute_path(task_file)
                    if os.path.exists(task_file_path):
                        logger.info(f"Copy {task_file_path} to {upload_workdir}")
                        shutil.copy(task_file_path, str(upload_workdir))
                        available_file_paths.append(os.path.join("upload_files", os.path.basename(task_file_path)))

            # Create BrowserUseAgent for each task
            if available_file_paths:
                upload_files_md = '\n'.join(available_file_paths)
                bu_task = task_description + f"\nNecessary files for this task:\n{upload_files_md}\n"
            else:
                bu_task = task_description
            bu_tasks[i] = bu_task
            # Create step callback for this agent
            step_callback = create_browser_agent_step_callback(state, agent_name)
            agent = BrowserUseAgent(
                task=bu_task,
                llm=state.vibesurf_agent.llm,
                browser_session=agent_browser_sessions[i],
                tools=bu_tools,
                task_id=f"{task_id}-{i + 1:03d}",
                file_system_path=str(bu_agent_workdir),
                register_new_step_callback=step_callback,
                extend_system_message=EXTEND_BU_SYSTEM_PROMPT,
                token_cost_service=state.vibesurf_agent.token_cost_service,
                flash_mode=state.vibesurf_agent.settings.agent_mode == "flash",
                use_thinking=state.vibesurf_agent.settings.agent_mode == "thinking"
            )
            agents.append(agent)

            # Track agent in VibeSurfAgent for control coordination
            if state.vibesurf_agent and hasattr(state.vibesurf_agent, '_running_agents'):
                state.vibesurf_agent._running_agents[agent_id] = agent
                logger.debug(f"🔗 Registered parallel agent {agent_id} for control coordination")

        except Exception as e:
            import traceback
            traceback.print_exc()
            logger.error(f"❌ Failed to create agent {agent_id}: {e}")
            await log_agent_activity(state, agent_name, "error",
                                     f"Failed to create agent: {str(e)}")

    # Execute all agents in parallel
    try:
        histories = await asyncio.gather(*[agent.run() for agent in agents], return_exceptions=True)

        # Process results
        results = []
        for i, (agent, history) in enumerate(zip(agents, histories)):
            task = bu_tasks[i]
            bu_agent_workdir = f"bu_agents/{task_id}-{i + 1:03d}"
            agent_name = f"browser_use_agent-{task_id}-{i + 1:03d}"

            important_files = []
            if history and history.history and len(history.history[-1].result) > 0:
                last_result = history.history[-1].result[-1]
                important_files = last_result.attachments
                if important_files:
                    important_files = [os.path.join(bu_agent_workdir, file_name) for file_name in important_files]

            if isinstance(history, Exception):
                results.append(BrowserTaskResult(
                    agent_id=f"{task_id}-{i + 1:03d}",
                    task=task,
                    success=False,
                    error=str(history),
                    agent_workdir=bu_agent_workdir,
                    important_files=important_files,
                ))
                # Log error
                await log_agent_activity(state, agent_name, "error", f"Task failed: {str(history)}")
            else:
                results.append(BrowserTaskResult(
                    agent_id=f"{task_id}-{i + 1:03d}",
                    task=task,
                    agent_workdir=bu_agent_workdir,
                    success=history.is_successful(),
                    important_files=important_files,
                    result=history.final_result() if hasattr(history, 'final_result') else "Task completed",
                    error=str(history.errors()) if history.has_errors() and not history.is_successful() else ""
                ))
                # Log result
                if history.is_successful():
                    result_text = history.final_result()
                    await log_agent_activity(state, agent_name, "result",
                                             f"Task completed successfully: \n{result_text}")
                else:
                    error_text = str(history.errors())
                    await log_agent_activity(state, agent_name, "error", f"Task failed: {error_text}")

        return results

    except Exception as e:
        import traceback
        traceback.print_exc()

    finally:
        # Remove agents from control tracking and cleanup browser sessions
        for i, agent_id in enumerate(bu_agent_ids):
            if pending_tasks[i].get('tab_id', None) is None:
                await state.vibesurf_agent.browser_manager.unregister_agent(agent_id, close_tabs=True)
            if state.vibesurf_agent and hasattr(state.vibesurf_agent, '_running_agents'):
                state.vibesurf_agent._running_agents.pop(agent_id, None)
                logger.debug(f"🔗 Unregistered parallel agent {agent_id} from control coordination")


async def execute_single_browser_tasks(state: VibeSurfState) -> BrowserTaskResult | None:
    """Execute pending tasks in single mode one by one"""
    logger.info("🔄 Executing pending tasks in single mode...")
    task_info = state.browser_tasks[0]
    task_id = nanoid.generate(size=5)
    bu_agents_workdir = state.vibesurf_agent.file_system.get_dir() / "bu_agents"
    bu_agents_workdir.mkdir(parents=True, exist_ok=True)
    task_description = task_info.get('task', '')
    if not task_description:
        return BrowserTaskResult(
            agent_id=f"{task_id}-{1:03d}",
            task='',
            agent_workdir=f"bu_agents/{task_id}-{1:03d}",
            success=False,
            error="Task description is empty. Please provide a valid task description for browser use agent.",
        )

    task_files = task_info.get('task_files', [])
    bu_agent_workdir = bu_agents_workdir / f"{task_id}-{1:03d}"
    bu_agent_workdir.mkdir(parents=True, exist_ok=True)
    agent_name = f"browser_use_agent-{task_id}-{1:03d}"
    agent_id = f"bu_agent-{task_id}-{1:03d}"
    # Log agent creation
    await log_agent_activity(state, agent_name, "working", f"{task_description}")

    try:
        vibesurf_tools = state.vibesurf_agent.tools
        bu_tools = BrowserUseTools()
        # for mcp_server_name, mcp_client in vibesurf_tools.mcp_clients.items():
        #     await mcp_client.register_to_tools(
        #         tools=bu_tools,
        #         prefix=f"mcp.{mcp_server_name}."
        #     )
        available_file_paths = []
        if task_files:
            for task_file in task_files:
                upload_workdir = bu_agent_workdir / "upload_files"
                upload_workdir.mkdir(parents=True, exist_ok=True)
                task_file_path = state.vibesurf_agent.file_system.get_absolute_path(task_file)
                if os.path.exists(task_file_path):
                    logger.info(f"Copy {task_file_path} to {upload_workdir}")
                    shutil.copy(task_file_path, str(upload_workdir))
                    available_file_paths.append(os.path.join("upload_files", os.path.basename(task_file_path)))

        # Create BrowserUseAgent for each task
        if available_file_paths:
            upload_files_md = '\n'.join(available_file_paths)
            bu_task = task_description + f"\nNecessary files for this task:\n{upload_files_md}\n"
        else:
            bu_task = task_description

        step_callback = create_browser_agent_step_callback(state, agent_name)
        main_browser_session = state.vibesurf_agent.browser_manager.main_browser_session
        if task_info.get("tab_id", None):
            tab_id = task_info.get("tab_id")
            target_id = await main_browser_session.get_target_id_from_tab_id(tab_id)
            await main_browser_session.get_or_create_cdp_session(target_id=target_id)
        else:
            new_target = await main_browser_session.cdp_client.send.Target.createTarget(
                params={'url': 'chrome://newtab/'})
            target_id = new_target["targetId"]
            await main_browser_session.get_or_create_cdp_session(target_id=target_id)
        agent = BrowserUseAgent(
            task=bu_task,
            llm=state.vibesurf_agent.llm,
            browser_session=main_browser_session,
            tools=bu_tools,
            task_id=f"{task_id}-{1:03d}",
            file_system_path=str(bu_agent_workdir),
            register_new_step_callback=step_callback,
            extend_system_message=EXTEND_BU_SYSTEM_PROMPT,
            token_cost_service=state.vibesurf_agent.token_cost_service,
            flash_mode=state.vibesurf_agent.settings.agent_mode == "flash",
            use_thinking=state.vibesurf_agent.settings.agent_mode == "thinking"
        )
        if state.vibesurf_agent and hasattr(state.vibesurf_agent, '_running_agents'):
            state.vibesurf_agent._running_agents[agent_id] = agent
            logger.debug(f"🔗 Registered single agent {agent_id} for control coordination")

        history = await agent.run()
        bu_agent_workdir = f"bu_agents/{task_id}-{1:03d}"
        important_files = []
        if history and history.history and len(history.history[-1].result) > 0:
            last_result = history.history[-1].result[-1]
            important_files = last_result.attachments
            if important_files:
                important_files = [os.path.join(bu_agent_workdir, file_name) for file_name in important_files]

        result = BrowserTaskResult(
            agent_id=agent_id,
            agent_workdir=bu_agent_workdir,
            task=bu_task,
            important_files=important_files,
            success=history.is_successful(),
            result=history.final_result() if hasattr(history, 'final_result') else "Task completed",
            error=str(history.errors()) if history.has_errors() and not history.is_successful() else ""
        )

        # Log result
        if result.success:
            await log_agent_activity(state, agent_name, "result",
                                     f"Task completed successfully: \n{result.result}")
        else:
            await log_agent_activity(state, agent_name, "error",
                                     f"Task failed: {result.error}")
        return result

    except Exception as e:
        import traceback
        traceback.print_exc()

        bu_agent_workdir = f"bu_agents/{task_id}-{1:03d}"
        return BrowserTaskResult(
            agent_id=agent_id,
            agent_workdir=bu_agent_workdir,
            task=task_description,
            success=False,
            error=str(e)
        )
    finally:
        # Remove agent from control tracking
        if state.vibesurf_agent and hasattr(state.vibesurf_agent, '_running_agents'):
            state.vibesurf_agent._running_agents.pop(agent_id, None)
            logger.debug(f"🔗 Unregistered single agent {agent_id} from control coordination")


async def report_task_execution_node(state: VibeSurfState) -> VibeSurfState:
    """
    Execute HTML report generation task assigned by supervisor agent
    """
    return await control_aware_node(_report_task_execution_node_impl, state, "report_task_execution")


async def _report_task_execution_node_impl(state: VibeSurfState) -> VibeSurfState:
    """Implementation of report task execution node"""
    logger.info("📄 Executing HTML report generation task...")

    agent_name = "report_writer_agent"

    # Log agent activity
    await log_agent_activity(state, agent_name, "working", "Generating HTML report")

    try:
        # Create step callback for report writer agent
        step_callback = create_report_writer_step_callback(state, agent_name)

        # Use ReportWriterAgent to generate HTML report
        report_writer = ReportWriterAgent(
            llm=state.vibesurf_agent.llm,
            workspace_dir=str(state.vibesurf_agent.file_system.get_dir()),
            step_callback=step_callback,
            use_thinking=state.vibesurf_agent.settings.agent_mode == "thinking",
        )
        
        # Register report writer agent for control coordination
        agent_id = "report_writer_agent"
        if state.vibesurf_agent and hasattr(state.vibesurf_agent, '_running_agents'):
            state.vibesurf_agent._running_agents[agent_id] = report_writer
            logger.debug(f"🔗 Registered report writer agent for control coordination")
        
        try:
            action_params = state.action_params
            report_task = action_params.get('task', [])
            report_information = {
                "browser_results": [bu_result.model_dump() for bu_result in state.browser_results if bu_result]
            }
            report_data = {
                "report_task": report_task,
                "report_information": report_information
            }

            report_result = await report_writer.generate_report(report_data)
            state.generated_report_result = report_result

            # Return to vibesurf agent for next decision
            state.current_step = "vibesurf_agent"

            if report_result.success:
                await log_agent_activity(state, agent_name, "result",
                                         f"✅ HTML report generated successfully: {report_result.msg}\nPath: `{report_result.report_path}`")
                logger.info(f"✅ Report generated successfully: {report_result.report_path}")
            else:
                await log_agent_activity(state, agent_name, "error",
                                         f"❌ Report generation failed: {report_result.msg}\nPath: `{report_result.report_path}`")
                logger.warning(f"⚠️ Report generation failed: {report_result.msg}")
                
        finally:
            # Remove report writer agent from control tracking
            if state.vibesurf_agent and hasattr(state.vibesurf_agent, '_running_agents'):
                state.vibesurf_agent._running_agents.pop(agent_id, None)
                logger.debug(f"🔗 Unregistered report writer agent from control coordination")
                
        return state

    except Exception as e:
        logger.error(f"❌ Report generation failed: {e}")
        state.current_step = "vibesurf_agent"
        await log_agent_activity(state, agent_name, "error", f"Report generation failed: {str(e)}")
        return state


def route_after_vibesurf_agent(state: VibeSurfState) -> str:
    """Route based on vibesurf agent decisions"""
    if state.current_step == "browser_task_execution":
        return "browser_task_execution"
    elif state.current_step == "report_task_execution":
        return "report_task_execution"
    elif state.current_step == "vibesurf_agent":
        return "vibesurf_agent"  # Continue in vibesurf agent loop
    elif state.is_complete:
        return "END"  # task_done sets is_complete=True, go directly to END
    else:
        return "END"  # Default fallback - complete workflow


def route_after_browser_task_execution(state: VibeSurfState) -> str:
    """Route back to vibesurf agent after browser task completion"""
    return "vibesurf_agent"


def route_after_report_task_execution(state: VibeSurfState) -> str:
    """Route back to vibesurf agent after report task completion"""
    return "vibesurf_agent"


def should_continue(state: VibeSurfState) -> str:
    """Main continuation logic"""
    if state.is_complete:
        return "END"
    else:
        return "continue"


def create_vibe_surf_workflow() -> StateGraph:
    """Create the simplified LangGraph workflow with supervisor agent as core tools"""

    workflow = StateGraph(VibeSurfState)

    # Add nodes for simplified architecture
    workflow.add_node("vibesurf_agent", vibesurf_agent_node)
    workflow.add_node("browser_task_execution", browser_task_execution_node)
    workflow.add_node("report_task_execution", report_task_execution_node)

    # Set entry point
    workflow.set_entry_point("vibesurf_agent")

    # VibeSurf agent routes to different execution nodes or END
    workflow.add_conditional_edges(
        "vibesurf_agent",
        route_after_vibesurf_agent,
        {
            "browser_task_execution": "browser_task_execution",
            "report_task_execution": "report_task_execution",
            "vibesurf_agent": "vibesurf_agent",
            "END": END
        }
    )

    # Execution nodes return to vibesurf agent
    workflow.add_conditional_edges(
        "browser_task_execution",
        route_after_browser_task_execution,
        {
            "vibesurf_agent": "vibesurf_agent"
        }
    )

    workflow.add_conditional_edges(
        "report_task_execution",
        route_after_report_task_execution,
        {
            "vibesurf_agent": "vibesurf_agent"
        }
    )

    return workflow


class VibeSurfAgent:
    """Main LangGraph-based VibeSurf Agent"""

    def __init__(
            self,
            llm: BaseChatModel,
            browser_manager: BrowserManager,
            tools: VibeSurfTools,
            workspace_dir: str = "./workspace",
            settings: Optional[VibeSurfAgentSettings] = None,
            extend_system_prompt: Optional[str] = None,
    ):
        """Initialize VibeSurfAgent with required components"""
        self.llm: BaseChatModel = llm
        self.settings = settings or VibeSurfAgentSettings()
        self.token_cost_service = TokenCost(include_cost=self.settings.calculate_cost)
        self.token_cost_service.register_llm(llm)
        self.browser_manager: BrowserManager = browser_manager
        self.tools: VibeSurfTools = tools
        self.workspace_dir = workspace_dir
        os.makedirs(self.workspace_dir, exist_ok=True)
        self.extend_system_prompt = extend_system_prompt
        self.cur_session_id = None
        self.file_system: Optional[CustomFileSystem] = None
        self.message_history = []
        self.activity_logs = []

        # Create LangGraph workflow
        self.workflow = create_vibe_surf_workflow()
        self.app = self.workflow.compile()

        # Control state management
        self._control_lock = asyncio.Lock()
        self._current_state: Optional[VibeSurfState] = None
        self._running_agents: Dict[str, Any] = {}  # Track running BrowserUseAgent instances
        self._execution_task: Optional[asyncio.Task] = None

        logger.info("🌊 VibeSurf Agent initialized with LangGraph workflow")
        
        # Initialize telemetry
        self.telemetry = ProductTelemetry()

    def load_message_history(self, session_id: Optional[str] = None) -> list:
        """Load message history for a specific session, or return [] for new sessions"""
        if session_id is None:
            return []

        session_message_history_path = os.path.join(self.workspace_dir, "sessions", session_id, "message_history.pkl")

        if not os.path.exists(session_message_history_path):
            all_message_history_path = os.path.join(self.workspace_dir, "message_history.pkl")
            if os.path.exists(all_message_history_path):
                with open(all_message_history_path, "rb") as f:
                    message_history_dict = pickle.load(f)
                if session_id in message_history_dict:
                    return message_history_dict[session_id]
            logger.info(f"No message history found for session {session_id}, creating new")
            return []

        try:
            with open(session_message_history_path, "rb") as f:
                message_history = pickle.load(f)
                logger.info(f"Loading message history for session {session_id} from {session_message_history_path}")
                return message_history
        except Exception as e:
            logger.error(f"Failed to load message history for session {session_id}: {e}")
            return []

    def save_message_history(self, session_id: Optional[str] = None):
        """Save message history for a specific session"""
        if session_id is None:
            return

        # Create session directory if it doesn't exist
        session_dir = os.path.join(self.workspace_dir, "sessions", session_id)
        os.makedirs(session_dir, exist_ok=True)

        session_message_history_path = os.path.join(session_dir, "message_history.pkl")

        try:
            with open(session_message_history_path, "wb") as f:
                logger.info(f"Saving message history for session {session_id} to {session_message_history_path}")
                pickle.dump(self.message_history, f)
        except Exception as e:
            logger.error(f"Failed to save message history for session {session_id}: {e}")

    def load_activity_logs(self, session_id: Optional[str] = None) -> list:
        """Load activity logs for a specific session, or return [] for new sessions"""
        if session_id is None:
            return []

        session_activity_logs_path = os.path.join(self.workspace_dir, "sessions", session_id, "activity_logs.pkl")

        if not os.path.exists(session_activity_logs_path):
            # Adaptive to the older version
            all_activity_logs_path = os.path.join(self.workspace_dir, "activity_logs.pkl")
            if os.path.exists(all_activity_logs_path):
                with open(all_activity_logs_path, "rb") as f:
                    activity_logs_dict = pickle.load(f)
                if session_id in activity_logs_dict:
                    return activity_logs_dict[session_id]
            logger.info(f"No activity logs found for session {session_id}, creating new")
            return []

        try:
            with open(session_activity_logs_path, "rb") as f:
                activity_logs = pickle.load(f)
                logger.info(f"Loading activity logs for session {session_id} from {session_activity_logs_path}")
                return activity_logs
        except Exception as e:
            logger.error(f"Failed to load activity logs for session {session_id}: {e}")
            return []

    def save_activity_logs(self, session_id: Optional[str] = None):
        """Save activity logs for a specific session"""
        if session_id is None:
            return

        # Create session directory if it doesn't exist
        session_dir = os.path.join(self.workspace_dir, "sessions", session_id)
        os.makedirs(session_dir, exist_ok=True)

        session_activity_logs_path = os.path.join(session_dir, "activity_logs.pkl")

        try:
            with open(session_activity_logs_path, "wb") as f:
                logger.info(f"Saving activity logs for session {session_id} to {session_activity_logs_path}")
                pickle.dump(self.activity_logs, f)
        except Exception as e:
            logger.error(f"Failed to save activity logs for session {session_id}: {e}")

    async def stop(self, reason: str = None) -> ControlResult:
        """
        Stop the vibesurf execution immediately
        
        Args:
            reason: Optional reason for stopping
            
        Returns:
            ControlResult with operation status
        """
        try:
            async with self._control_lock:
                reason = reason or "Manual stop requested"
                logger.info(f"🛑 Stopping agent execution: {reason}")

                self.message_history.append(UserMessage(
                    content=f"🛑 Stopping agent execution: {reason}"))

                if self._current_state:
                    self._current_state.should_stop = True
                    self._current_state.stopped = True

                # Stop all running agents with timeout
                try:
                    await asyncio.wait_for(self._stop_all_agents(), timeout=3.0)
                except asyncio.TimeoutError:
                    logger.warning("⚠️ Agent stopping timed out, continuing with task cancellation")

                # Cancel execution task if running
                if self._execution_task and not self._execution_task.done():
                    self._execution_task.cancel()
                    try:
                        await asyncio.wait_for(self._execution_task, timeout=2.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        logger.debug("🛑 Execution task cancelled or timed out")

                logger.info(f"✅ VibeSurf execution stopped: {reason}")
                return ControlResult(
                    success=True,
                    message=f"VibeSurf stopped successfully: {reason}",
                    details={"reason": reason}
                )

        except asyncio.TimeoutError:
            error_msg = f"Stop operation timed out after 10 seconds"
            logger.error(error_msg)
            return ControlResult(
                success=False,
                message=error_msg,
                details={"timeout": True}
            )
        except Exception as e:
            error_msg = f"Failed to stop VibeSurf: {str(e)}"
            logger.error(error_msg)
            return ControlResult(
                success=False,
                message=error_msg,
                details={"error": str(e)}
            )

    async def pause(self, reason: str = None) -> ControlResult:
        """
        Pause the VibeSurf execution
        
        Args:
            reason: Optional reason for pausing
            
        Returns:
            ControlResult with operation status
        """
        async with self._control_lock:
            try:
                reason = reason or "Manual pause requested"
                logger.info(f"⏸️ Pausing agent execution: {reason}")

                self.message_history.append(UserMessage(
                    content=f"⏸️ Pausing agent execution: {reason}"))

                if self._current_state:
                    self._current_state.should_pause = True

                # Pause all running agents
                await self._pause_all_agents()

                logger.info(f"✅ VibeSurf execution paused: {reason}")
                return ControlResult(
                    success=True,
                    message=f"VibeSurf paused successfully: {reason}",
                    details={"reason": reason}
                )

            except Exception as e:
                error_msg = f"Failed to pause VibeSurf: {str(e)}"
                logger.error(error_msg)
                return ControlResult(
                    success=False,
                    message=error_msg,
                    details={"error": str(e)}
                )

    async def resume(self, reason: str = None) -> ControlResult:
        """
        Resume the VibeSurf execution
        
        Args:
            reason: Optional reason for resuming
            
        Returns:
            ControlResult with operation status
        """
        async with self._control_lock:
            try:
                reason = reason or "Manual resume requested"
                logger.info(f"▶️ Resuming agent execution: {reason}")

                self.message_history.append(UserMessage(
                    content=f"▶️ Resuming agent execution: {reason}"))

                if self._current_state:
                    self._current_state.paused = False
                    self._current_state.should_pause = False

                # Resume all paused agents
                await self._resume_all_agents()

                logger.info(f"✅ VibeSurf execution resumed: {reason}")
                return ControlResult(
                    success=True,
                    message=f"VibeSurf resumed successfully: {reason}",
                    details={"reason": reason}
                )

            except Exception as e:
                error_msg = f"Failed to resume VibeSurf: {str(e)}"
                logger.error(error_msg)
                return ControlResult(
                    success=False,
                    message=error_msg,
                    details={"error": str(e)}
                )

    async def pause_agent(self, agent_id: str, reason: str = None) -> ControlResult:
        """
        Pause a specific agent
        
        Args:
            agent_id: ID of the agent to pause
            reason: Optional reason for pausing
            
        Returns:
            ControlResult with operation status
        """
        async with self._control_lock:
            try:
                reason = reason or f"Manual pause requested for agent {agent_id}"
                logger.info(f"⏸️ Pausing agent {agent_id}: {reason}")

                # Pause the specific agent if it's running
                agent = self._running_agents.get(agent_id)
                if agent:
                    if hasattr(agent, 'pause'):
                        await agent.pause()
                        logger.info(f"✅ Agent {agent_id} paused successfully")
                else:
                    logger.warning(f"⚠️ Agent {agent_id} not found")

                return ControlResult(
                    success=True,
                    message=f"Agent {agent_id} paused successfully: {reason}",
                    details={"agent_id": agent_id, "reason": reason}
                )

            except Exception as e:
                error_msg = f"Failed to pause agent {agent_id}: {str(e)}"
                logger.error(error_msg)
                return ControlResult(
                    success=False,
                    message=error_msg,
                    details={"agent_id": agent_id, "error": str(e)}
                )

    async def resume_agent(self, agent_id: str, reason: str = None) -> ControlResult:
        """
        Resume a specific agent
        
        Args:
            agent_id: ID of the agent to resume
            reason: Optional reason for resuming
            
        Returns:
            ControlResult with operation status
        """
        async with self._control_lock:
            try:
                reason = reason or f"Manual resume requested for agent {agent_id}"
                logger.info(f"▶️ Resuming agent {agent_id}: {reason}")

                # Resume the specific agent if it's running
                agent = self._running_agents.get(agent_id)
                if agent:
                    if hasattr(agent, 'resume'):
                        await agent.resume()
                        logger.info(f"✅ Agent {agent_id} resumed successfully")
                else:
                    logger.warning(f"⚠️ Agent {agent_id} not found")

                return ControlResult(
                    success=True,
                    message=f"Agent {agent_id} resumed successfully: {reason}",
                    details={"agent_id": agent_id, "reason": reason}
                )

            except Exception as e:
                error_msg = f"Failed to resume agent {agent_id}: {str(e)}"
                logger.error(error_msg)
                return ControlResult(
                    success=False,
                    message=error_msg,
                    details={"agent_id": agent_id, "error": str(e)}
                )

    def get_status(self) -> VibeSurfStatus:
        """
        Get current status of the VibeSurf and all agents
        
        Returns:
            VibeSurfStatus with current state information
        """
        try:
            # Determine overall status
            if not self._current_state:
                overall_status = "idle"
            elif self._current_state.stopped:
                overall_status = "stopped"
            elif self._current_state.paused or self._current_state.should_pause:
                overall_status = "paused"
            elif self._current_state.is_complete:
                overall_status = "completed"
            else:
                overall_status = "running"

            # Build agent statuses
            agent_statuses = {}

            # Add status for tracked running agents
            for agent_id, agent in self._running_agents.items():
                status = "running"
                current_action = None
                error_message = None
                pause_reason = None

                # Simplified status checking since paused_agents removed
                if self._current_state and self._current_state.stopped:
                    status = "stopped"
                elif self._current_state and self._current_state.paused:
                    status = "paused"

                # Get current action if available
                if agent and hasattr(agent, 'state'):
                    try:
                        if hasattr(agent.state, 'last_result') and agent.state.last_result:
                            current_action = f"Last action completed"
                        else:
                            current_action = "Executing task"
                    except:
                        current_action = "Unknown"

                agent_statuses[agent_id] = AgentStatus(
                    agent_id=agent_id,
                    status=status,
                    current_action=current_action,
                    error_message=error_message,
                    pause_reason=pause_reason
                )

            # Build progress information
            progress = {}
            if self._current_state:
                progress = {
                    "current_step": self._current_state.current_step,
                    "is_complete": self._current_state.is_complete,
                    "browser_tasks_count": len(self._current_state.browser_tasks),
                    "browser_results_count": len(self._current_state.browser_results)
                }

            return VibeSurfStatus(
                overall_status=overall_status,
                agent_statuses=agent_statuses,
                progress=progress,
                active_step=self._current_state.current_step if self._current_state else None
            )

        except Exception as e:
            logger.error(f"❌ Failed to get status: {e}")
            return VibeSurfStatus(
                overall_status="error",
                agent_statuses={},
                progress={"error": str(e)}
            )

    async def _stop_all_agents(self) -> None:
        """Stop all running agents"""
        for agent_id, agent in self._running_agents.items():
            try:
                # Also try to pause if available as a fallback
                if agent and hasattr(agent, 'stop'):
                    await agent.stop()
                    logger.info(f"⏸️ stop agent {agent_id}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to stop agent {agent_id}: {e}")

    async def _pause_all_agents(self) -> None:
        """Pause all running agents"""
        for agent_id, agent in self._running_agents.items():
            try:
                if hasattr(agent, 'pause'):
                    await agent.pause()
                    logger.info(f"⏸️ Paused agent {agent_id}")
                    # Note: paused_agents removed in simplified state
            except Exception as e:
                logger.warning(f"⚠️ Failed to pause agent {agent_id}: {e}")

    async def _resume_all_agents(self) -> None:
        """Resume all paused agents"""
        for agent_id, agent in self._running_agents.items():
            try:
                if hasattr(agent, 'resume'):
                    await agent.resume()
                    logger.info(f"▶️ Resumed agent {agent_id}")
                    # Note: paused_agents removed in simplified state
            except Exception as e:
                logger.warning(f"⚠️ Failed to resume agent {agent_id}: {e}")

    def _create_sub_agent_prompt(self, new_task: str, agent_id: str) -> str:
        """
        Create a generic prompt for sub-agents when receiving new tasks.
        This prompt is designed to work with any type of sub-agent.
        """
        return f"""🔄 **New Task/Guidance from User:**

{new_task}

**Note:** As a sub-agent, you should evaluate whether this new task is relevant to your current work. You may:
- **Use it** if it provides helpful guidance, tips, or corrections for your current task
- **Use it** if it's a follow-up task that enhances your current work
- **Ignore it** if it's unrelated to your specific responsibilities or doesn't apply to your current task

Please continue with your assigned work, incorporating this guidance only if it's relevant and helpful to your specific role and current task."""

    async def add_new_task(self, new_task: str) -> None:
        """
        Add a new task or follow-up instruction during execution.
        This can be user feedback, guidance, or additional requirements.

        Args:
            new_task: The new task, guidance, or instruction from the user
        """
        activity_entry = {
            "agent_name": 'user',
            "agent_status": 'additional_request',  # working, result, error
            "agent_msg": f"{new_task}",
            "timestamp": datetime.now().isoformat()
        }
        self.activity_logs.append(activity_entry)

        # Create an English prompt for the main agent
        prompt = f"""🔄 **New Task/Follow-up from User:**

{new_task}

**Instructions:** This is additional guidance, a follow-up task, or user feedback to help with the current task execution. Please analyze how this relates to the current task and proceed accordingly."""

        # Add to VibeSurf agent's message history
        self.message_history.append(UserMessage(content=prompt))
        logger.info(f"🌊 VibeSurf agent received new task: {new_task}")

        # Propagate to all running sub-agents with generic sub-agent prompt
        if self._running_agents:
            logger.info(f"📡 Propagating new task to {len(self._running_agents)} running agents")
            for agent_id, agent in self._running_agents.items():
                try:
                    if hasattr(agent, 'add_new_task'):
                        # Use the generic sub-agent prompt
                        sub_agent_prompt = self._create_sub_agent_prompt(new_task, agent_id)
                        agent.add_new_task(sub_agent_prompt)
                        logger.debug(f"✅ Sent new task to agent {agent_id}")
                    else:
                        logger.debug(f"⚠️ Agent {agent_id} doesn't support add_new_task")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to send new task to agent {agent_id}: {e}")
        else:
            logger.debug("📭 No running agents to propagate new task to")

    async def process_upload_files(self, upload_files: Optional[List[str]] = None):
        if not upload_files:
            return []
        new_upload_files = []
        for ufile_path in upload_files:
            # timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            dst_filename = f"upload_files/{os.path.basename(ufile_path)}"
            new_upload_files.append(dst_filename)
        return new_upload_files

    def format_upload_files(self, upload_files: Optional[List[str]] = None, use_abspath: bool = False) -> str:
        """Format uploaded file for LLM prompt"""
        if upload_files is None:
            return ""
        if use_abspath:
            file_urls = []
            for i, file_path in enumerate(upload_files):
                abs_file_path = self.file_system.get_absolute_path(file_path)
                normalized_path = abs_file_path.replace(os.path.sep, '/')
                file_url = f"{i + 1}. [{os.path.basename(file_path)}](file:///{normalized_path})"
                file_urls.append(file_url)
            return "\n".join(file_urls)
        else:
            return "\n".join(
                [f"{i + 1}. {file_path}" for i, file_path in enumerate(upload_files)])

    async def run(
            self,
            task: str,
            upload_files: Optional[List[str]] = None,
            session_id: Optional[str] = None,
            agent_mode: str = "thinking"
    ) -> str | None:
        """
        Main execution method that returns markdown summary with control capabilities
        
        Args:
            task: User task to execute
            upload_files: Optional list of file paths that user has uploaded
            
        Returns:
            str: Markdown summary of execution results
        """
        logger.info(f"🚀 Starting VibeSurfAgent execution for task: {task}. Powered by LLM model: {self.llm.model_name}")
        
        # Capture telemetry start event
        start_time = time.time()
        import vibe_surf
        start_event = VibeSurfAgentTelemetryEvent(
            version=vibe_surf.__version__,
            action='start',
            task_description=task if task else None,  # Limit task description length
            model=getattr(self.llm, 'model_name', None),
            model_provider=getattr(self.llm, 'provider', None),
            session_id=session_id
        )
        self.telemetry.capture(start_event)
        
        try:
            self.settings.agent_mode = agent_mode
            session_id = session_id or self.cur_session_id or uuid7str()
            if session_id != self.cur_session_id:
                # Load session-specific data when switching sessions
                self.cur_session_id = session_id
                self.message_history = self.load_message_history(session_id)
                self.activity_logs = self.load_activity_logs(session_id)
                session_dir = os.path.join(self.workspace_dir, "sessions", self.cur_session_id)
                os.makedirs(session_dir, exist_ok=True)
                self.file_system = CustomFileSystem(session_dir)
                self.token_cost_service.clear_history()

            if upload_files and not isinstance(upload_files, list):
                upload_files = [upload_files]
            upload_files = await self.process_upload_files(upload_files)

            if not self.message_history:
                vibesurf_system_prompt = VIBESURF_SYSTEM_PROMPT
                if self.extend_system_prompt:
                    vibesurf_system_prompt += f"\n Extend System Prompt provided by user:\n {self.extend_system_prompt}"

                self.message_history.append(SystemMessage(content=vibesurf_system_prompt))

                action = self.tools.registry.registry.actions["get_all_toolkit_types"]
                # Execute the tool
                result = await action.function()
                self.message_history.append(UserMessage(content=result.extracted_content))
                logger.debug(result.extracted_content)
                self.message_history.append(UserMessage(content="Before you use these toolkits. Please use `search_tool` to filter tools that match the user's requirements and Use `get_tool_info` to retrieve detailed parameter information if you are not confidence."))

            # Format processed upload files for prompt
            user_request = f"* User's New Request:\n{task}\n"
            if upload_files:
                upload_files_md = self.format_upload_files(upload_files)
                user_request += f"* User Uploaded Files:\n{upload_files_md}\n"
            self.message_history.append(
                UserMessage(content=user_request)
            )
            logger.info(user_request)

            abs_upload_files_md = self.format_upload_files(upload_files, use_abspath=True)
            activity_entry = {
                "agent_name": 'user',
                "agent_status": 'request',  # working, result, error
                "agent_msg": f"{task}\nUpload Files:\n{abs_upload_files_md}\n" if upload_files else f"{task}"
            }
            self.activity_logs.append(activity_entry)

            latest_version = await check_latest_vibesurf_version()
            current_version = get_vibesurf_version()
            if latest_version and latest_version != current_version:
                update_msg = f'📦 Newer version of vibesurf available: {latest_version} (current: {current_version}). \nUpgrade with: \n`uv pip install vibesurf -U`\nor\nDownload [Windows Installer](https://github.com/vibesurf-ai/VibeSurf/releases/latest/download/vibesurf-windows-x64.exe).\n\nYou can find more information at [release page](https://github.com/vibesurf-ai/VibeSurf/releases).'
                logger.debug(update_msg)
                activity_update_tip = {
                    "agent_name": 'System',
                    "agent_status": 'tip',  # working, result, error
                    "agent_msg": update_msg
                }
                self.activity_logs.append(activity_update_tip)

            # Initialize state first (needed for file processing)
            initial_state = VibeSurfState(
                original_task=task,
                upload_files=upload_files or [],
                session_id=session_id,
                current_workspace_dir=os.path.join(self.workspace_dir, "sessions", self.cur_session_id),
                vibesurf_agent=self,
            )

            # Set current state for control operations
            async with self._control_lock:
                self._current_state = initial_state
                self._running_agents.clear()  # Clear any previous agents

            async def _execute_workflow():
                """Internal workflow execution with proper state management"""
                try:
                    # Run without checkpoints
                    logger.info("🔄 Executing LangGraph workflow...")
                    return await self.app.ainvoke(initial_state)
                finally:
                    # Clean up running agents
                    async with self._control_lock:
                        self._running_agents.clear()

            # Execute workflow as a task for control management
            self._execution_task = asyncio.create_task(_execute_workflow())
            final_state = await self._execution_task

            # Update current state reference
            async with self._control_lock:
                self._current_state = final_state

            # Get final result
            result = await self._get_result(final_state)
            logger.info("✅ VibeSurfAgent execution completed")
            
            # Capture telemetry completion event
            end_time = time.time()
            duration = end_time - start_time
            completion_event = VibeSurfAgentTelemetryEvent(
                version=vibe_surf.__version__,
                action='task_completed',
                task_description=task if task else None,
                model=getattr(self.llm, 'model_name', None),
                model_provider=getattr(self.llm, 'provider', None),
                duration_seconds=duration,
                success=True,
                session_id=session_id
            )
            self.telemetry.capture(completion_event)
            self.telemetry.flush()
            
            return result

        except asyncio.CancelledError:
            logger.info("🛑 VibeSurfAgent execution was cancelled")
            # Add cancellation activity log
            if self.activity_logs:
                activity_entry = {
                    "agent_name": "VibeSurfAgent",
                    "agent_status": "cancelled",
                    "agent_msg": "Task execution was cancelled by user request."
                }
                self.activity_logs.append(activity_entry)
            return f"# Task Execution Cancelled\n\n**Task:** {task}\n\nExecution was stopped by user request."
        except Exception as e:
            import traceback
            traceback.print_exc()
            logger.error(f"❌ VibeSurfAgent execution failed: {e}")
            
            # Capture telemetry error event
            end_time = time.time()
            duration = end_time - start_time
            error_event = VibeSurfAgentTelemetryEvent(
                version=vibe_surf.__version__,
                action='error',
                task_description=BrowserTaskResult if task else None,
                model=getattr(self.llm, 'model_name', None),
                model_provider=getattr(self.llm, 'provider', None),
                duration_seconds=duration,
                success=False,
                error_message=str(e),  # Limit error message length
                session_id=session_id
            )
            self.telemetry.capture(error_event)
            self.telemetry.flush()
            
            # Add error activity log
            if self.activity_logs:
                activity_entry = {
                    "agent_name": "VibeSurfAgent",
                    "agent_status": "error",
                    "agent_msg": f"Task execution failed: {str(e)}"
                }
                self.activity_logs.append(activity_entry)
            return f"# Task Execution Failed\n\n**Task:** {task}\n\n**Error:** {str(e)}\n\nPlease try again or contact support."
        finally:

            activity_entry = {
                "agent_name": "VibeSurfAgent",
                "agent_status": "done",  # working, result, error
                "agent_msg": "Finish Task."
            }
            self.activity_logs.append(activity_entry)
            # Save session-specific data
            if self.cur_session_id:
                self.save_message_history(self.cur_session_id)
                self.save_activity_logs(self.cur_session_id)
            async with self._control_lock:
                self._current_state = None
                self._execution_task = None
                self._running_agents.clear()

    def get_activity_logs(self, session_id: Optional[str] = None, message_index: Optional[int] = None) -> Optional[
        List[Dict]]:
        if session_id is None:
            session_id = self.cur_session_id

        # Ensure session_id exists in activity_logs
        if session_id != self.cur_session_id:
            session_logs = self.load_activity_logs(session_id)
        else:
            session_logs = self.activity_logs

        logger.debug(f"📋 Session {session_id} has {len(session_logs)} activity logs")

        if message_index is None:
            logger.debug(f"📤 Returning all {len(session_logs)} activity logs for session {session_id}")
            return session_logs
        else:
            if message_index >= len(session_logs):
                logger.debug(
                    f"⚠️ Message index {message_index} out of range for session {session_id} (max index: {len(session_logs) - 1})")
                return None
            else:
                activity_log = session_logs[message_index]
                logger.debug(
                    f"📤 Returning activity log at index {message_index}: {activity_log.get('agent_name', 'unknown')} - {activity_log.get('agent_status', 'unknown')}")
                return activity_log

    async def _get_result(self, state) -> str:
        """Get the final result from execution with simplified workflow support"""
        # Handle both dict and dataclass state types due to LangGraph serialization
        final_response = state.get('final_response') if isinstance(state, dict) else getattr(state, 'final_response',
                                                                                             None)
        original_task = state.get('original_task') if isinstance(state, dict) else getattr(state, 'original_task',
                                                                                           'Unknown task')
        if final_response:
            return final_response
        else:
            return f"# Task Execution Completed\n\n**Task:** {original_task}\n\nTask execution completed but no detailed result available."


workflow = create_vibe_surf_workflow()
