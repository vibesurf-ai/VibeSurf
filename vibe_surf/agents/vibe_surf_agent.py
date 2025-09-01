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

from vibe_surf.agents.browser_use_agent import BrowserUseAgent
from vibe_surf.agents.report_writer_agent import ReportWriterAgent

from vibe_surf.agents.prompts.vibe_surf_prompt import (
    SUPERVISOR_AGENT_SYSTEM_PROMPT,
)
from vibe_surf.browser.browser_manager import BrowserManager
from vibe_surf.controller.vibesurf_controller import VibeSurfController

logger = logging.getLogger(__name__)


class TodoItem(BaseModel):
    """Individual todo item with simple string-based task description"""
    task: str = Field(description="Simple task description")
    status: Literal["pending", "in_progress", "completed"] = "pending"
    assigned_agent_id: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None


class ExecutionMode(BaseModel):
    """Execution mode configuration"""
    mode: Literal["single", "parallel"] = "single"
    reason: str = Field(description="LLM reasoning for mode selection")


class BrowserTaskResult(BaseModel):
    """Result from browser task execution"""
    agent_id: str
    task: str
    success: bool
    result: Optional[str] = None
    error: Optional[str] = None
    screenshots: List[str] = Field(default_factory=list)
    extracted_data: Optional[str] = None


class ReportRequirement(BaseModel):
    """Indicates if and what type of report is needed"""
    needs_report: bool = False
    report_type: Literal["summary", "detailed", "none"] = "none"
    reason: str = Field(description="LLM reasoning for report decision")


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
    """Main LangGraph state for VibeSurfAgent workflow with simplified architecture"""

    # Core task information
    original_task: str = ""
    upload_files: List[str] = field(default_factory=list)
    session_id: str = field(default_factory=lambda: uuid7str())
    task_id: str = field(default_factory=lambda: uuid7str())

    # Workflow state
    current_step: str = "task_analysis"
    is_simple_response: bool = False

    # Supervisor Agent - Core controller with message history
    supervisor_message_history: List[BaseMessage] = field(default_factory=list)
    supervisor_action: Optional[str] = None

    # Todo list management
    todo_list: List[TodoItem] = field(default_factory=list)
    completed_todos: List[TodoItem] = field(default_factory=list)
    current_task_index: int = 0

    # Task execution
    execution_mode: Optional[ExecutionMode] = None
    pending_tasks: List[str] = field(default_factory=list)
    pending_todo_indices: List[int] = field(default_factory=list)  # Track which todo indices are being executed
    browser_results: List[BrowserTaskResult] = field(default_factory=list)  # record all browser result
    prev_browser_results: List[BrowserTaskResult] = field(default_factory=list)  # record previous browser result

    # Response outputs
    simple_response: Optional[str] = None
    generated_report_path: Optional[str] = None
    final_summary: Optional[str] = None
    is_complete: bool = False

    # File organization
    workspace_dir: str = "./workspace"
    session_dir: Optional[str] = None
    task_dir: Optional[str] = None

    # Integration components
    browser_manager: Optional[BrowserManager] = None
    vibesurf_controller: Optional[VibeSurfController] = None
    llm: Optional[BaseChatModel] = None
    vibesurf_agent: Optional[Any] = None

    # Control state management
    paused: bool = False
    stopped: bool = False
    should_pause: bool = False
    should_stop: bool = False

    # Agent control tracking
    agent_control_states: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    paused_agents: set = field(default_factory=set)

    # Control metadata
    control_timestamps: Dict[str, datetime] = field(default_factory=dict)
    control_reasons: Dict[str, str] = field(default_factory=dict)
    last_control_action: Optional[str] = None

    # Agent activity log
    agent_activity_logs: List[Dict[str, str]] = field(default_factory=list)


# Utility functions for parsing LLM JSON responses
def parse_json_response(response_text: str, fallback_data: Dict) -> Dict:
    """Parse JSON response with repair capability"""
    try:
        # Try to find JSON in the response
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1

        if json_start >= 0 and json_end > json_start:
            json_text = response_text[json_start:json_end]
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                # Try to repair JSON
                repaired_json = repair_json(json_text)
                return json.loads(repaired_json)

        # If no JSON found, return fallback
        return fallback_data
    except Exception as e:
        logger.warning(f"JSON parsing failed: {e}, using fallback")
        return fallback_data


def parse_task_analysis_response(response_text: str) -> Dict:
    """Parse task analysis JSON response for simple response detection"""
    fallback = {
        "is_simple_response": False,
        "reasoning": "Failed to parse response, defaulting to complex task",
        "simple_response_content": None
    }
    return parse_json_response(response_text, fallback)


def parse_supervisor_response(response_text: str) -> Dict:
    """Parse supervisor agent JSON response"""
    fallback = {
        "action": "summary_generation",
        "reasoning": "Failed to parse response, defaulting to summary generation",
        "todo_items": [],
        "task_type": "single",
        "tasks_to_execute": [],
        "summary_content": None
    }
    result = parse_json_response(response_text, fallback)

    # Ensure todo_items is always a list for actions that modify todos
    if result.get("action") in ["generate_todos", "update_todos"]:
        if "todo_items" not in result or not isinstance(result["todo_items"], list):
            result["todo_items"] = []

    return result


def parse_todo_generation_response(response_text: str) -> List[str]:
    """Parse todo generation JSON response"""
    fallback = {
        "todo_items": ["Complete the original task"]
    }
    result = parse_json_response(response_text, fallback)
    return result.get("todo_items", fallback["todo_items"])[:5]  # Max 5 items


def parse_execution_planning_response(response_text: str) -> ExecutionMode:
    """Parse execution planning JSON response"""
    fallback = {
        "execution_mode": "single",
        "reasoning": "Default single mode"
    }
    result = parse_json_response(response_text, fallback)

    return ExecutionMode(
        mode=result.get("execution_mode", "single"),
        reason=result.get("reasoning", "Default execution mode")
    )


def parse_todo_update_response(response_text: str) -> Dict:
    """Parse todo update JSON response"""
    fallback = {
        "additional_tasks": [],
        "next_action": "summary_generation",
        "reasoning": "Default action"
    }
    return parse_json_response(response_text, fallback)


def parse_report_decision_response(response_text: str) -> ReportRequirement:
    """Parse report decision JSON response"""
    fallback = {
        "needs_report": False,
        "report_type": "none",
        "reasoning": "Default no report"
    }
    result = parse_json_response(response_text, fallback)

    return ReportRequirement(
        needs_report=result.get("needs_report", False),
        report_type=result.get("report_type", "none"),
        reason=result.get("reasoning", "Default report decision")
    )


def format_upload_files_list(upload_files: Optional[List[str]] = None) -> str:
    """Format uploaded file list for LLM prompt"""
    if upload_files is None:
        return ""
    return "\n".join(
        [f"{i + 1}. [{os.path.basename(file_path)}](file:///{file_path})" for i, file_path in enumerate(upload_files)])


def format_todo_list(todo_list: List[TodoItem]) -> str:
    """Format todo list for LLM prompt"""
    return "\n".join([f"{i + 1}. {item.task}" for i, item in enumerate(todo_list)])


def format_completed_todos(completed_todos: List[TodoItem]) -> str:
    """Format completed todos for LLM prompt"""
    return "\n".join([f"✅ {item.task} - {item.result or 'Completed'}" for item in completed_todos])


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


def format_todo_list_markdown(todo_list: List[TodoItem]) -> str:
    """Format todo list as markdown"""
    if not todo_list:
        return "No todo items"

    markdown_lines = []
    for i, item in enumerate(todo_list):
        if item.status == "completed":
            status_symbol = "- [x] "
        else:
            status_symbol = "- [ ] "
        markdown_lines.append(f"{status_symbol}{item.task}")

    return "\n".join(markdown_lines)


def log_agent_activity(state: VibeSurfState, agent_name: str, agent_status: str, agent_msg: str) -> None:
    """Log agent activity to the activity log"""
    activity_entry = {
        "agent_name": agent_name,
        "agent_status": agent_status,  # working, result, error
        "agent_msg": agent_msg
    }
    state.agent_activity_logs.append(activity_entry)
    logger.info(f"📝 Logged activity: {agent_name} - {agent_status}:\n{agent_msg}")


def create_browser_agent_step_callback(state: VibeSurfState, agent_name: str):
    """Create a step callback function for browser-use agent to log each step"""
    
    def step_callback(browser_state_summary, agent_output, step_num: int) -> None:
        """Callback function to log browser agent step information"""
        try:
            # Format step information as markdown
            step_msg = f"## Step {step_num}\n\n"
            
            # Add thinking if present
            if agent_output.thinking:
                step_msg += f"**💡 Thinking:**\n{agent_output.thinking}\n\n"
            
            # Add evaluation if present
            if agent_output.evaluation_previous_goal:
                step_msg += f"**👍 Evaluation:**\n{agent_output.evaluation_previous_goal}\n\n"
            
            # Add memory if present
            # if agent_output.memory:
            #     step_msg += f"**🧠 Memory:** {agent_output.memory}\n\n"
            
            # Add next goal if present
            if agent_output.next_goal:
                step_msg += f"**🎯 Next Goal:**\n{agent_output.next_goal}\n\n"
            
            # Add action summary
            if agent_output.action and len(agent_output.action) > 0:
                action_count = len(agent_output.action)
                step_msg += f"**⚡ Actions:**\n"
                
                # Add brief action details
                for i, action in enumerate(agent_output.action):  # Limit to first 3 actions to avoid too much detail
                    action_data = action.model_dump(exclude_unset=True)
                    action_name = next(iter(action_data.keys())) if action_data else 'unknown'
                    action_params = json.dumps(action_data[action_name], ensure_ascii=False) if action_name in action_data else ""
                    step_msg += f"- [x] {action_name}: {action_params}\n"
            else:
                step_msg += f"**⚡ Actions:** No actions\n"
            
            # Log the step activity
            log_agent_activity(state, agent_name, "working", step_msg.strip())
            
        except Exception as e:
            logger.error(f"❌ Error in step callback for {agent_name}: {e}")
            # Log a simple fallback message
            log_agent_activity(state, agent_name, "step", f"Step {step_num} completed")
    
    return step_callback


def ensure_directories(state: VibeSurfState) -> None:
    """Ensure proper directory structure"""
    # Create session directory: workspace_dir/session_id/
    state.session_dir = os.path.join(state.workspace_dir, state.session_id)
    os.makedirs(state.session_dir, exist_ok=True)

    # Create task directory: workspace_dir/session_id/task_id/
    state.task_dir = os.path.join(state.session_dir, state.task_id)
    os.makedirs(state.task_dir, exist_ok=True)

    # Create subdirectories for different output types
    os.makedirs(os.path.join(state.task_dir, "screenshots"), exist_ok=True)
    os.makedirs(os.path.join(state.task_dir, "reports"), exist_ok=True)
    os.makedirs(os.path.join(state.task_dir, "logs"), exist_ok=True)


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
            state.control_timestamps["paused"] = datetime.now()

        logger.debug(f"⏸️ Node {node_name} waiting - workflow paused")
        await asyncio.sleep(0.5)  # Check every 500ms

        # Allow stopping while paused
        if state.stopped or state.should_stop:
            logger.info(f"🛑 Node {node_name} stopped while paused")
            state.stopped = True
            state.should_stop = False
            state.control_timestamps["stopped"] = datetime.now()
            return state

    # Check for stop signal
    if state.should_stop:
        logger.info(f"🛑 Node {node_name} stopping workflow")
        state.stopped = True
        state.should_stop = False
        state.control_timestamps["stopped"] = datetime.now()
        return state

    # Execute the actual node
    logger.debug(f"▶️ Executing node: {node_name}")
    state.last_control_action = f"executing_{node_name}"

    try:
        return await node_func(state)
    except Exception as e:
        logger.error(f"❌ Node {node_name} failed: {e}")
        raise


# LangGraph Nodes

async def supervisor_agent_node(state: VibeSurfState) -> VibeSurfState:
    """
    Core supervisor agent node - manages todos, assigns tasks, and coordinates workflow
    """
    return await control_aware_node(_supervisor_agent_node_impl, state, "supervisor_agent")


def format_browser_tabs(tabs: Optional[List[TabInfo]] = None) -> str:
    if not tabs:
        return ""
    return "\n".join([f"[{i}] Page Title: {item.title}, Page Url: {item.url}, Page ID: {item.target_id}" for i, item in enumerate(tabs)])


async def _supervisor_agent_node_impl(state: VibeSurfState) -> VibeSurfState:
    """Implementation of supervisor agent node - core workflow controller"""
    logger.info("🎯 Supervisor Agent: Managing workflow and task coordination...")

    supervisor_message_history = state.supervisor_message_history

    # Build supervisor user prompt with current context
    if state.prev_browser_results:
        browser_results_md = format_browser_results(state.prev_browser_results)
        supervisor_message_history.append(AssistantMessage(
            content=f"Previous Browser Execution Results: \n{browser_results_md}"))
    elif state.generated_report_path:
        supervisor_message_history.append(AssistantMessage(content=f"Generated Report Path: {state.generated_report_path}"))

    if state.todo_list:
        supervisor_message_history.append(UserMessage(
            content=f"Completed Todos:\n{format_completed_todos(state.completed_todos)}\nCurrent Todos:\n{format_todo_list(state.todo_list)}"))

    browser_tabs = await state.browser_manager.main_browser_session.get_tabs()
    browser_tabs_md = format_browser_tabs(browser_tabs)
    if browser_tabs_md:
        supervisor_message_history.append(UserMessage(
            content=f"Available Browser Tabs:\n{browser_tabs_md}"))

    # Reset prev_browser_results
    state.prev_browser_results = []
    try:
        response = await state.llm.ainvoke(supervisor_message_history)
        # add result to message history
        supervisor_message_history.append(AssistantMessage(content=response.completion))

        supervisor_result = parse_supervisor_response(response.completion)

        action = supervisor_result["action"]
        reasoning = supervisor_result["reasoning"]
        # Log agent activity
        log_agent_activity(state, "supervisor_agent", "thinking", f"{reasoning}")

        state.supervisor_action = action

        logger.info(f"🎯 Supervisor decision: {action} - {reasoning}")

        # Handle different actions
        if action == "generate_todos":
            # Generate initial todos
            todo_items = supervisor_result.get("todo_items", [])
            if todo_items:
                state.todo_list = [TodoItem(task=task) for task in todo_items]
                todo_todo_list_md = format_todo_list_markdown(state.todo_list)
                supervisor_message_history.append(
                    UserMessage(content=f"Successfully generated todo list:\n{todo_todo_list_md}"))
                log_agent_activity(state, "supervisor_agent", "result", f"Todo List:\n\n{todo_todo_list_md}")
            # Continue in supervisor to assign tasks
            state.current_step = "supervisor_agent"

        elif action == "update_todos":
            # Replace all remaining todos with the new list
            todo_items = supervisor_result.get("todo_items", [])
            if todo_items:
                # Clear current todo list and replace with new items
                state.todo_list = [TodoItem(task=task) for task in todo_items]
                todo_todo_list_md = format_todo_list_markdown(state.completed_todos + state.todo_list)
                supervisor_message_history.append(
                    UserMessage(content=f"Successfully Updated todo list:\n{todo_todo_list_md}"))
                log_agent_activity(state, "supervisor_agent", "result", f"Todo List:\n\n{todo_todo_list_md}")
            else:
                # If no todo_items provided, clear the list
                state.todo_list = []
                todo_todo_list_md = format_todo_list_markdown(state.completed_todos + state.todo_list)
                supervisor_message_history.append(
                    UserMessage(content=f"Cleared todo list - all tasks completed:\n{todo_todo_list_md}"))
                log_agent_activity(state, "supervisor_agent", "result",
                                   f"Cleared todo list - all tasks completed\n{todo_todo_list_md}")

            # Continue in supervisor to assign tasks
            state.current_step = "supervisor_agent"

        elif action == "assign_browser_task":
            # Assign browser tasks
            task_type = supervisor_result.get("task_type", "single")
            tasks_to_execute = supervisor_result.get("tasks_to_execute", [])

            if tasks_to_execute:
                tasks_to_execute_new = []
                todo_indices = []  # Track which todo items are being executed
                
                for task_item in tasks_to_execute:
                    if isinstance(task_item, list):
                        # Format: [page_index, todo_index]
                        page_index, todo_index = task_item
                        if todo_index < len(state.todo_list):
                            task_description = state.todo_list[todo_index].task
                            tasks_to_execute_new.append([browser_tabs[page_index].target_id, task_description])
                            todo_indices.append(todo_index)
                    else:
                        # Format: todo_index
                        todo_index = task_item
                        if todo_index < len(state.todo_list):
                            task_description = state.todo_list[todo_index].task
                            tasks_to_execute_new.append(task_description)
                            todo_indices.append(todo_index)
                
                state.execution_mode = ExecutionMode(
                    mode=task_type,
                    reason=reasoning
                )
                state.pending_tasks = tasks_to_execute_new
                state.pending_todo_indices = todo_indices  # Store which todo indices are being executed
                state.current_step = "browser_task_execution"

                log_agent_activity(state, "supervisor_agent", "result",
                                   f"Assigned {len(tasks_to_execute)} browser tasks ({task_type} mode)")
            else:
                # No tasks to execute, continue in supervisor
                state.current_step = "supervisor_agent"
                supervisor_message_history.append(
                    UserMessage(content=f"No tasks to execute. Please provide browser tasks to execute."))

        elif action == "assign_report_task":
            # Assign report generation task
            state.current_step = "report_task_execution"
            log_agent_activity(state, "supervisor_agent", "result", "Assigned report generation task")

        elif action == "simple_response":
            # Use provided content or generate if not provided
            state.current_step = "simple_response"
            state.simple_response = supervisor_result["simple_response_content"]
            state.is_complete = True
            log_agent_activity(state, "supervisor_agent", "result", state.simple_response)
        elif action == "summary_generation":
            # Handle summary generation directly in supervisor
            summary_content = supervisor_result.get("summary_content")

            if summary_content:
                # Use LLM-provided summary content
                state.final_summary = summary_content
                state.is_complete = True
                state.current_step = "summary_generation"
                log_agent_activity(state, "supervisor_agent", "result", f"{summary_content}")
            else:
                # Generate summary using the same logic as the old summary generation node
                state.current_step = "supervisor_agent"
                supervisor_message_history.append(
                    UserMessage(content=f"The summary content is empty. Please provide summary content if you think all requirements have been accomplished."))
        else:
            # Unknown action, default to complete workflow
            state.current_step = "summary_generation"
            log_agent_activity(state, "supervisor_agent", "error", f"Unknown action: {action}")

        return state

    except Exception as e:
        logger.error(f"❌ Supervisor agent failed: {e}")
        state.current_step = "summary_generation"
        log_agent_activity(state, "supervisor_agent", "error", f"Supervisor failed: {str(e)}")
        return state


async def browser_task_execution_node(state: VibeSurfState) -> VibeSurfState:
    """
    Execute browser tasks assigned by supervisor agent
    """
    return await control_aware_node(_browser_task_execution_node_impl, state, "browser_task_execution")


async def _browser_task_execution_node_impl(state: VibeSurfState) -> VibeSurfState:
    """Implementation of browser task execution node"""
    logger.info("🚀 Executing browser tasks assigned by supervisor...")

    # Log agent activity
    log_agent_activity(state, "browser_task_executor", "working",
                       f"Executing {len(state.pending_tasks)} browser tasks in {state.execution_mode.mode if state.execution_mode else 'single'} mode")

    # Setup file organization
    ensure_directories(state)

    try:
        if state.execution_mode and state.execution_mode.mode == "parallel":
            # Execute tasks in parallel
            results = await execute_parallel_browser_tasks(state)
        else:
            # Execute tasks in single mode
            results = await execute_single_browser_tasks(state)

        # Update browser results
        state.prev_browser_results = copy.deepcopy(results)
        state.browser_results.extend(results)

        # Mark corresponding todos as completed using indices
        for i, todo_index in enumerate(state.pending_todo_indices):
            if todo_index < len(state.todo_list) and state.todo_list[todo_index].status != "completed":
                todo = state.todo_list[todo_index]
                todo.status = "completed"
                if i < len(results):
                    todo.result = results[i].result if results[i].success else None
                    todo.error = results[i].error if not results[i].success else None
                state.completed_todos.append(todo)

        # Remove completed todos from the todo list
        # Sort indices in reverse order to avoid index shifting issues
        for todo_index in sorted(state.pending_todo_indices, reverse=True):
            if todo_index < len(state.todo_list):
                state.todo_list.pop(todo_index)

        # Clear pending tasks and indices
        state.pending_tasks = []
        state.pending_todo_indices = []

        # Return to supervisor for next decision
        state.current_step = "supervisor_agent"

        # Log result
        successful_tasks = sum(1 for result in results if result.success)
        log_agent_activity(state, "browser_task_executor", "result",
                           f"Browser execution completed: {successful_tasks}/{len(results)} tasks successful")

        logger.info(f"✅ Browser task execution completed with {len(results)} results")
        return state

    except Exception as e:
        logger.error(f"❌ Browser task execution failed: {e}")

        # Create error results for pending tasks
        error_results = []
        for i, task in enumerate(state.pending_tasks):
            # Get the actual task description for the error result
            if isinstance(task, list):
                task_description = task[1]  # [target_id, task_description]
            else:
                task_description = task
            error_results.append(BrowserTaskResult(
                agent_id="error",
                task=task_description,
                success=False,
                error=str(e)
            ))

        state.browser_results.extend(error_results)
        state.pending_tasks = []
        state.pending_todo_indices = []
        state.current_step = "supervisor_agent"

        log_agent_activity(state, "browser_task_executor", "error", f"Browser execution failed: {str(e)}")
        return state


async def report_task_execution_node(state: VibeSurfState) -> VibeSurfState:
    """
    Execute HTML report generation task assigned by supervisor agent
    """
    return await control_aware_node(_report_task_execution_node_impl, state, "report_task_execution")


async def _report_task_execution_node_impl(state: VibeSurfState) -> VibeSurfState:
    """Implementation of report task execution node"""
    logger.info("📄 Executing HTML report generation task...")

    # Log agent activity
    log_agent_activity(state, "report_task_executor", "working", "Generating HTML report")

    try:
        # Use ReportWriterAgent to generate HTML report
        report_writer = ReportWriterAgent(
            llm=state.llm,
            workspace_dir=state.task_dir
        )

        report_data = {
            "original_task": state.original_task,
            "execution_results": state.browser_results,
            "report_type": "detailed",  # Default to detailed report
            "upload_files": state.upload_files
        }

        report_path = await report_writer.generate_report(report_data)

        state.generated_report_path = report_path

        # Return to supervisor for next decision
        state.current_step = "supervisor_agent"

        log_agent_activity(state, "report_task_executor", "result",
                           f"HTML report generated successfully at: `{report_path}`")

        logger.info(f"✅ Report generated: {report_path}")
        return state

    except Exception as e:
        logger.error(f"❌ Report generation failed: {e}")
        state.current_step = "supervisor_agent"
        log_agent_activity(state, "report_task_executor", "error", f"Report generation failed: {str(e)}")
        return state


async def execute_parallel_browser_tasks(state: VibeSurfState) -> List[BrowserTaskResult]:
    """Execute pending tasks in parallel using multiple browser agents"""
    logger.info("🔄 Executing pending tasks in parallel...")

    # Register agents with browser manager
    agents = []
    pending_tasks = state.pending_tasks
    bu_agent_ids = []
    register_sessions = []
    for i, task in enumerate(pending_tasks):
        agent_id = f"agent-{i + 1}-{state.task_id[-4:]}"
        if isinstance(task, list):
            target_id, task_description = task
        else:
            task_description = task
            target_id = None
        register_sessions.append(
            state.browser_manager.register_agent(agent_id, target_id=target_id)
        )
        bu_agent_ids.append(agent_id)
    agent_browser_sessions = await asyncio.gather(*register_sessions)

    for i, task in enumerate(pending_tasks):
        agent_id = f"agent-{i + 1}-{state.task_id[-4:]}"
        if isinstance(task, list):
            target_id, task_description = task
        else:
            task_description = task
        try:
            # Log agent creation
            log_agent_activity(state, f"browser_use_agent-{i + 1}-{state.task_id[-4:]}", "working",
                               f"{task_description}")

            # Create BrowserUseAgent for each task
            if state.upload_files:
                upload_files_md = format_upload_files_list(state.upload_files)
                bu_task = task_description + f"\nAvailable uploaded files:\n{upload_files_md}\n"
            else:
                bu_task = task_description
            
            # Create step callback for this agent
            agent_name = f"browser_use_agent-{i + 1}-{state.task_id[-4:]}"
            step_callback = create_browser_agent_step_callback(state, agent_name)
            
            agent = BrowserUseAgent(
                task=bu_task,
                llm=state.llm,
                browser_session=agent_browser_sessions[i],
                controller=state.vibesurf_controller,
                task_id=f"{state.task_id}-{i + 1}",
                file_system_path=state.task_dir,
                register_new_step_callback=step_callback,
                extend_system_message="Please make sure the language of your output in JSON value should remain the same as the user's request or task.",
                preload=False
            )
            agents.append(agent)

            # Track agent in VibeSurfAgent for control coordination
            if state.vibesurf_agent and hasattr(state.vibesurf_agent, '_running_agents'):
                state.vibesurf_agent._running_agents[agent_id] = agent
                logger.debug(f"🔗 Registered parallel agent {agent_id} for control coordination")

        except Exception as e:
            logger.error(f"❌ Failed to create agent {agent_id}: {e}")
            log_agent_activity(state, f"browser_use_agent-{i + 1}-{state.task_id[-4:]}", "error",
                               f"Failed to create agent: {str(e)}")

    # Execute all agents in parallel
    try:
        histories = await asyncio.gather(*[agent.run() for agent in agents], return_exceptions=True)

        # Process results
        results = []
        for i, (agent, history) in enumerate(zip(agents, histories)):
            agent_id = f"agent-{i + 1}-{state.task_id[-4:]}"
            if isinstance(history, Exception):
                results.append(BrowserTaskResult(
                    agent_id=f"agent-{i + 1}",
                    task=pending_tasks[i],
                    success=False,
                    error=str(history)
                ))
                # Log error
                log_agent_activity(state, f"browser_use_agent-{i + 1}-{state.task_id[-4:]}", "error",
                                   f"Task failed: {str(history)}")
            else:
                results.append(BrowserTaskResult(
                    agent_id=f"agent-{i + 1}",
                    task=pending_tasks[i],
                    success=history.is_successful(),
                    result=history.final_result() if hasattr(history, 'final_result') else "Task completed",
                    error=str(history.errors()) if history.has_errors() and not history.is_successful() else ""
                ))
                # Log result
                if history.is_successful():
                    result_text = history.final_result() if hasattr(history, 'final_result') else "Task completed"
                    log_agent_activity(state, f"browser_use_agent-{i + 1}-{state.task_id[-4:]}", "result",
                                       f"Task completed successfully: \n{result_text}")
                else:
                    error_text = str(history.errors()) if history.has_errors() else "Unknown error"
                    log_agent_activity(state, f"browser_use_agent-{i + 1}-{state.task_id[-4:]}", "error",
                                       f"Task failed: {error_text}")

        return results

    finally:
        # Remove agents from control tracking and cleanup browser sessions
        for i, agent_id in enumerate(bu_agent_ids):
            if not isinstance(pending_tasks[i], list):
                await state.browser_manager.unregister_agent(agent_id, close_tabs=True)
            if state.vibesurf_agent and hasattr(state.vibesurf_agent, '_running_agents'):
                state.vibesurf_agent._running_agents.pop(agent_id, None)
                logger.debug(f"🔗 Unregistered parallel agent {agent_id} from control coordination")


async def execute_single_browser_tasks(state: VibeSurfState) -> List[BrowserTaskResult]:
    """Execute pending tasks in single mode one by one"""
    logger.info("🔄 Executing pending tasks in single mode...")

    results = []
    for i, task in enumerate(state.pending_tasks):
        if isinstance(task, list):
            target_id, task_description = task
        else:
            task_description = task
        logger.info(f"🔄 Executing task ({i + 1}/{len(state.pending_tasks)}): {task_description}")

        agent_id = f"agent-single-{state.task_id[-4:]}-{i}"

        # Log agent activity
        log_agent_activity(state, f"browser_use_agent-{state.task_id[-4:]}", "working", f"{task_description}")

        try:
            await state.browser_manager._get_active_target()
            if state.upload_files:
                upload_files_md = format_upload_files_list(state.upload_files)
                bu_task = task_description + f"\nAvailable user uploaded files:\n{upload_files_md}\n"
            else:
                bu_task = task_description
            # Create step callback for this agent
            agent_name = f"browser_use_agent-{state.task_id[-4:]}"
            step_callback = create_browser_agent_step_callback(state, agent_name)
            
            agent = BrowserUseAgent(
                task=bu_task,
                llm=state.llm,
                browser_session=state.browser_manager.main_browser_session,
                controller=state.vibesurf_controller,
                task_id=f"{state.task_id}-{i}",
                file_system_path=state.task_dir,
                register_new_step_callback=step_callback,
                preload=False,
                extend_system_message="Please make sure the language of your output in JSON values should remain the same as the user's request or task."
            )

            # Track agent in VibeSurfAgent for control coordination
            if state.vibesurf_agent and hasattr(state.vibesurf_agent, '_running_agents'):
                state.vibesurf_agent._running_agents[agent_id] = agent
                logger.debug(f"🔗 Registered single agent {agent_id} for control coordination")

            try:
                history = await agent.run()

                result = BrowserTaskResult(
                    agent_id=agent_id,
                    task=task,
                    success=history.is_successful(),
                    result=history.final_result() if hasattr(history, 'final_result') else "Task completed",
                    error=str(history.errors()) if history.has_errors() and not history.is_successful() else ""
                )

                # Log result
                if result.success:
                    log_agent_activity(state, f"browser_use_agent-{state.task_id[-4:]}", "result",
                                       f"Task completed successfully: \n{result.result}")
                else:
                    log_agent_activity(state, f"browser_use_agent-{state.task_id[-4:]}", "error",
                                       f"Task failed: {result.error}")

                results.append(result)
            finally:
                # Remove agent from control tracking
                if state.vibesurf_agent and hasattr(state.vibesurf_agent, '_running_agents'):
                    state.vibesurf_agent._running_agents.pop(agent_id, None)
                    logger.debug(f"🔗 Unregistered single agent {agent_id} from control coordination")

        except Exception as e:
            logger.error(f"❌ Single task execution failed: {e}")
            log_agent_activity(state, f"browser_use_agent-{state.task_id[-4:]}", "error",
                               f"Task execution failed: {str(e)}")
            results.append(BrowserTaskResult(
                agent_id=agent_id,
                task=task,
                success=False,
                error=str(e)
            ))

    return results


def route_after_supervisor_agent(state: VibeSurfState) -> str:
    """Route based on supervisor agent decisions"""
    if state.current_step == "browser_task_execution":
        return "browser_task_execution"
    elif state.current_step == "report_task_execution":
        return "report_task_execution"
    elif state.current_step == "summary_generation":
        return "summary_generation"  # Summary generated, go to END
    elif state.current_step == "simple_response":
        return "simple_response"
    elif state.current_step == "supervisor_agent":
        return "supervisor_agent"  # Continue in supervisor loop
    else:
        return "END"  # Default fallback - complete workflow


def route_after_browser_task_execution(state: VibeSurfState) -> str:
    """Route back to supervisor after browser task completion"""
    return "supervisor_agent"


def route_after_report_task_execution(state: VibeSurfState) -> str:
    """Route back to supervisor after report task completion"""
    return "supervisor_agent"


def should_continue(state: VibeSurfState) -> str:
    """Main continuation logic"""
    if state.is_complete:
        return "END"
    else:
        return "continue"


def create_vibe_surf_workflow() -> StateGraph:
    """Create the simplified LangGraph workflow with supervisor agent as core controller"""

    workflow = StateGraph(VibeSurfState)

    # Add nodes for simplified architecture
    workflow.add_node("supervisor_agent", supervisor_agent_node)
    workflow.add_node("browser_task_execution", browser_task_execution_node)
    workflow.add_node("report_task_execution", report_task_execution_node)

    # Set entry point
    workflow.set_entry_point("supervisor_agent")

    # Supervisor agent routes to different execution nodes or END
    workflow.add_conditional_edges(
        "supervisor_agent",
        route_after_supervisor_agent,
        {
            "browser_task_execution": "browser_task_execution",
            "report_task_execution": "report_task_execution",
            "summary_generation": END,
            "supervisor_agent": "supervisor_agent",
            "simple_response": END,
            "END": END
        }
    )

    # Execution nodes return to supervisor
    workflow.add_conditional_edges(
        "browser_task_execution",
        route_after_browser_task_execution,
        {
            "supervisor_agent": "supervisor_agent"
        }
    )

    workflow.add_conditional_edges(
        "report_task_execution",
        route_after_report_task_execution,
        {
            "supervisor_agent": "supervisor_agent"
        }
    )

    return workflow


class VibeSurfAgent:
    """Main LangGraph-based VibeSurfAgent with comprehensive control capabilities"""

    def __init__(
            self,
            llm: BaseChatModel,
            browser_manager: BrowserManager,
            controller: VibeSurfController,
            workspace_dir: str = "./workspace",
    ):
        """Initialize VibeSurfAgent with required components"""
        self.llm = llm
        self.browser_manager = browser_manager
        self.controller = controller
        self.workspace_dir = workspace_dir
        os.makedirs(self.workspace_dir, exist_ok=True)
        self.cur_session_id = None
        self.message_history = self.load_message_history()
        self.activity_logs = self.load_activity_logs()

        # Create LangGraph workflow
        self.workflow = create_vibe_surf_workflow()
        self.app = self.workflow.compile()

        # Control state management
        self._control_lock = asyncio.Lock()
        self._current_state: Optional[VibeSurfState] = None
        self._running_agents: Dict[str, Any] = {}  # Track running BrowserUseAgent instances
        self._execution_task: Optional[asyncio.Task] = None

        logger.info("🌊 VibeSurfAgent initialized with LangGraph workflow and control capabilities")

    def load_message_history(self, message_history_path: Optional[str] = None):
        if message_history_path is None:
            message_history_path = os.path.join(self.workspace_dir, "message_history.pkl")
        if not os.path.exists(message_history_path):
            return defaultdict(list)
        with open(message_history_path, "rb") as f:
            message_history = pickle.load(f)
            logger.info(f"Loading message history from {message_history_path}")
            for session_id in message_history:
                logger.info(f"{session_id} has {len(message_history[session_id])} messages.")
        return message_history

    def save_message_history(self, message_history_path: Optional[str] = None):
        if message_history_path is None:
            message_history_path = os.path.join(self.workspace_dir, "message_history.pkl")

        with open(message_history_path, "wb") as f:
            logger.info(f"Saving message history with {len(self.message_history)} sessions to {message_history_path}")
            pickle.dump(self.message_history, f)

    def load_activity_logs(self, activity_logs_path: Optional[str] = None):
        if activity_logs_path is None:
            activity_logs_path = os.path.join(self.workspace_dir, "activity_logs.pkl")
        if not os.path.exists(activity_logs_path):
            return defaultdict(list)
        with open(activity_logs_path, "rb") as f:
            activity_logs = pickle.load(f)
            logger.info(f"Loading activity logs from {activity_logs_path}")
            for session_id in activity_logs:
                logger.info(f"{session_id} has {len(activity_logs[session_id])} activity logs.")
        return activity_logs

    def save_activity_logs(self, activity_logs_path: Optional[str] = None):
        if activity_logs_path is None:
            activity_logs_path = os.path.join(self.workspace_dir, "activity_logs.pkl")

        with open(activity_logs_path, "wb") as f:
            logger.info(f"Saving activity logs with {len(self.activity_logs)} sessions to {activity_logs_path}")
            pickle.dump(self.activity_logs, f)

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

                if self.cur_session_id in self.message_history:
                    supervisor_message_history = self.message_history[self.cur_session_id]
                    supervisor_message_history.append(UserMessage(
                        content=f"🛑 Stopping agent execution: {reason}"))

                if self._current_state:
                    self._current_state.should_stop = True
                    self._current_state.stopped = True
                    self._current_state.control_timestamps["stopped"] = datetime.now()
                    self._current_state.control_reasons["stopped"] = reason
                    self._current_state.last_control_action = "stop"

                # Stop all running agents with timeout
                try:
                    await asyncio.wait_for(self._stop_all_agents(reason), timeout=3.0)
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

                if self.cur_session_id in self.message_history:
                    supervisor_message_history = self.message_history[self.cur_session_id]
                    supervisor_message_history.append(UserMessage(
                        content=f"⏸️ Pausing agent execution: {reason}"))

                if self._current_state:
                    self._current_state.should_pause = True
                    self._current_state.control_timestamps["pause_requested"] = datetime.now()
                    self._current_state.control_reasons["paused"] = reason
                    self._current_state.last_control_action = "pause"

                # Pause all running agents
                await self._pause_all_agents(reason)

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

                if self.cur_session_id in self.message_history:
                    supervisor_message_history = self.message_history[self.cur_session_id]
                    supervisor_message_history.append(UserMessage(
                        content=f"▶️ Resuming agent execution: {reason}"))

                if self._current_state:
                    self._current_state.paused = False
                    self._current_state.should_pause = False
                    self._current_state.control_timestamps["resumed"] = datetime.now()
                    self._current_state.control_reasons["resumed"] = reason
                    self._current_state.last_control_action = "resume"

                # Resume all paused agents
                await self._resume_all_agents(reason)

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

                # Update state tracking
                if self._current_state:
                    self._current_state.paused_agents.add(agent_id)
                    if agent_id not in self._current_state.agent_control_states:
                        self._current_state.agent_control_states[agent_id] = {}
                    self._current_state.agent_control_states[agent_id]["paused"] = True
                    self._current_state.agent_control_states[agent_id]["pause_reason"] = reason
                    self._current_state.agent_control_states[agent_id]["pause_timestamp"] = datetime.now()

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

                # Update state tracking
                if self._current_state:
                    self._current_state.paused_agents.discard(agent_id)
                    if agent_id not in self._current_state.agent_control_states:
                        self._current_state.agent_control_states[agent_id] = {}
                    self._current_state.agent_control_states[agent_id]["paused"] = False
                    self._current_state.agent_control_states[agent_id]["resume_reason"] = reason
                    self._current_state.agent_control_states[agent_id]["resume_timestamp"] = datetime.now()

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
                overall_status = "idle"
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

                # Check if agent is paused
                if self._current_state and agent_id in self._current_state.paused_agents:
                    status = "paused"
                    agent_state = self._current_state.agent_control_states.get(agent_id, {})
                    pause_reason = agent_state.get("pause_reason")
                elif self._current_state and self._current_state.stopped:
                    status = "stopped"

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
                    "completed_todos": len(self._current_state.completed_todos),
                    "total_todos": len(self._current_state.todo_list),
                    "current_task_index": self._current_state.current_task_index,
                    "is_complete": self._current_state.is_complete,
                    "last_control_action": self._current_state.last_control_action
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

    async def _stop_all_agents(self, reason: str) -> None:
        """Stop all running agents"""
        for agent_id, agent in self._running_agents.items():
            try:
                # Also try to pause if available as a fallback
                if agent and hasattr(agent, 'stop'):
                    await agent.stop()
                    logger.debug(f"⏸️ stop agent {agent_id}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to stop agent {agent_id}: {e}")

    async def _pause_all_agents(self, reason: str) -> None:
        """Pause all running agents"""
        for agent_id, agent in self._running_agents.items():
            try:
                if hasattr(agent, 'pause'):
                    await agent.pause()
                    logger.debug(f"⏸️ Paused agent {agent_id}")
                    if self._current_state:
                        self._current_state.paused_agents.add(agent_id)
            except Exception as e:
                logger.warning(f"⚠️ Failed to pause agent {agent_id}: {e}")

    async def _resume_all_agents(self, reason: str) -> None:
        """Resume all paused agents"""
        for agent_id, agent in self._running_agents.items():
            try:
                if hasattr(agent, 'resume'):
                    await agent.resume()
                    logger.debug(f"▶️ Resumed agent {agent_id}")
                    if self._current_state:
                        self._current_state.paused_agents.discard(agent_id)
            except Exception as e:
                logger.warning(f"⚠️ Failed to resume agent {agent_id}: {e}")

    async def run(
            self,
            task: str,
            upload_files: Optional[List[str]] = None,
            session_id: Optional[str] = None,
    ) -> str:
        """
        Main execution method that returns markdown summary with control capabilities
        
        Args:
            task: User task to execute
            upload_files: Optional list of file paths that user has uploaded
            
        Returns:
            str: Markdown summary of execution results
        """
        logger.info(f"🚀 Starting VibeSurfAgent execution for task: {task[:100]}...")
        agent_activity_logs = None
        try:
            session_id = session_id or self.cur_session_id or uuid7str()
            if session_id != self.cur_session_id:
                self.cur_session_id = session_id

            if self.cur_session_id not in self.message_history:
                logger.info(f"{self.cur_session_id} not found in message_history, create a new one.")
                self.message_history[self.cur_session_id] = []
            supervisor_message_history = self.message_history[self.cur_session_id]
            if not supervisor_message_history:
                supervisor_message_history.append(SystemMessage(content=SUPERVISOR_AGENT_SYSTEM_PROMPT))
            if upload_files and not isinstance(upload_files, list):
                upload_files = [upload_files]
            upload_files_md = format_upload_files_list(upload_files)
            supervisor_message_history.append(
                UserMessage(
                    content=f"* User's New Request:\n{task}\n* Uploaded Files for Completing Task:\n{upload_files_md}\n")
            )
            logger.info(f"* User's New Request:\n{task}\n* Uploaded Files for Completing Task:\n{upload_files_md}\n")

            if self.cur_session_id not in self.activity_logs:
                self.activity_logs[self.cur_session_id] = []
            agent_activity_logs = self.activity_logs[self.cur_session_id]
            activity_entry = {
                "agent_name": 'user',
                "agent_status": 'request',  # working, result, error
                "agent_msg": f"{task}\nUpload Files:\n{upload_files_md}\n" if upload_files else f"{task}"
            }
            agent_activity_logs.append(activity_entry)

            # Initialize state
            initial_state = VibeSurfState(
                original_task=task,
                upload_files=upload_files or [],
                workspace_dir=self.workspace_dir,
                browser_manager=self.browser_manager,
                vibesurf_controller=self.controller,
                agent_activity_logs=agent_activity_logs,
                supervisor_message_history=supervisor_message_history,
                llm=self.llm,
                session_id=session_id,
                vibesurf_agent=self  # Reference to VibeSurfAgent for control coordination
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
            return result

        except asyncio.CancelledError:
            logger.info("🛑 VibeSurfAgent execution was cancelled")
            # Add cancellation activity log
            if agent_activity_logs:
                activity_entry = {
                    "agent_name": "VibeSurfAgent",
                    "agent_status": "cancelled",
                    "agent_msg": "Task execution was cancelled by user request."
                }
                agent_activity_logs.append(activity_entry)
            return f"# Task Execution Cancelled\n\n**Task:** {task}\n\nExecution was stopped by user request."
        except Exception as e:
            logger.error(f"❌ VibeSurfAgent execution failed: {e}")
            # Add error activity log
            if agent_activity_logs:
                activity_entry = {
                    "agent_name": "VibeSurfAgent",
                    "agent_status": "error",
                    "agent_msg": f"Task execution failed: {str(e)}"
                }
                agent_activity_logs.append(activity_entry)
            return f"# Task Execution Failed\n\n**Task:** {task}\n\n**Error:** {str(e)}\n\nPlease try again or contact support."
        finally:
            if agent_activity_logs:
                activity_entry = {
                    "agent_name": "VibeSurfAgent",
                    "agent_status": "done",  # working, result, error
                    "agent_msg": "Finish Task."
                }
                agent_activity_logs.append(activity_entry)
            # Reset state
            self.save_message_history()
            self.save_activity_logs()
            async with self._control_lock:
                self._current_state = None
                self._execution_task = None
                self._running_agents.clear()

    def get_activity_logs(self, session_id: Optional[str] = None, message_index: Optional[int] = None) -> Optional[
        List[Dict]]:
        if session_id is None:
            session_id = self.cur_session_id
        
        logger.info(f"📊 GET_ACTIVITY_LOGS DEBUG - Session: {session_id}, Message Index: {message_index}, Current Session: {self.cur_session_id}")
        
        # Ensure session_id exists in activity_logs
        if session_id not in self.activity_logs:
            logger.warning(f"⚠️ Session {session_id} not found in activity_logs. Available sessions: {list(self.activity_logs.keys())}")
            return None
            
        session_logs = self.activity_logs[session_id]
        logger.info(f"📋 Session {session_id} has {len(session_logs)} activity logs")
        
        if message_index is None:
            logger.info(f"📤 Returning all {len(session_logs)} activity logs for session {session_id}")
            return session_logs
        else:
            if message_index >= len(session_logs):
                logger.debug(f"⚠️ Message index {message_index} out of range for session {session_id} (max index: {len(session_logs) - 1})")
                return None
            else:
                activity_log = session_logs[message_index]
                logger.info(f"📤 Returning activity log at index {message_index}: {activity_log.get('agent_name', 'unknown')} - {activity_log.get('agent_status', 'unknown')}")
                return activity_log

    async def _get_result(self, state) -> str:
        """Get the final result from execution with simplified workflow support"""
        # Handle both dict and dataclass state types due to LangGraph serialization
        simple_response = state.get('simple_response') if isinstance(state, dict) else getattr(state, 'simple_response',
                                                                                               None)
        final_summary = state.get('final_summary') if isinstance(state, dict) else getattr(state, 'final_summary', None)
        original_task = state.get('original_task') if isinstance(state, dict) else getattr(state, 'original_task',
                                                                                           'Unknown task')

        # Fallback for cases where state doesn't support logging
        if simple_response:
            return f"# Response\n\n{simple_response}"
        elif final_summary:
            return final_summary
        else:
            return f"# Task Execution Completed\n\n**Task:** {original_task}\n\nTask execution completed but no detailed result available."

workflow = create_vibe_surf_workflow()
