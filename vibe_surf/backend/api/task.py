"""
VibeSurf Agent Execution Router

Handles task submission, execution control (pause/resume/stop), and status monitoring
for VibeSurf agents.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
import logging
import os
from datetime import datetime
from uuid_extensions import uuid7str

from ..database import get_db_session
from .models import TaskCreateRequest, TaskControlRequest

# Import global variables and functions from shared_state
from ..shared_state import (
    execute_task_background,
    is_task_running,
    get_active_task_info,
    clear_active_task,
)

from vibe_surf.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/status")
async def check_task_status():
    """Quick check if a task is currently running"""
    return {
        "has_active_task": is_task_running(),
        "active_task": get_active_task_info()
    }


@router.post("/submit")
async def submit_task(
        task_request: "TaskCreateRequest",
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db_session)
):
    """Submit new task for execution (single task mode)"""
    from ..database.queries import LLMProfileQueries
    from ..shared_state import workspace_dir, active_task, llm, current_llm_profile_name

    # Check if task is already running
    if is_task_running():
        current_task = get_active_task_info()
        return {
            "success": False,
            "message": "Cannot submit task: another task is currently running",
            "active_task": {
                "task_id": current_task.get("task_id"),
                "status": current_task.get("status"),
                "session_id": current_task.get("session_id"),
                "start_time": current_task.get("start_time").isoformat() if current_task.get("start_time") else None
            }
        }

    try:
        # Get LLM profile from database
        llm_profile = await LLMProfileQueries.get_profile_with_decrypted_key(db, task_request.llm_profile_name)
        if not llm_profile:
            active_task = None
            return {
                "success": False,
                "error": "llm_connection_failed",
                "message": f"Failed to get LLM profile with decrypted key {task_request.llm_profile_name}",
                "llm_profile": task_request.llm_profile_name
            }

        # Initialize LLM for this task if needed
        if not current_llm_profile_name or current_llm_profile_name != task_request.llm_profile_name:
            current_llm_profile_name = task_request.llm_profile_name
            success, message = await _ensure_llm_initialized(llm_profile)
            logger.info("Test LLM Connection!")
            if not success:
                active_task = None
                return {
                    "success": False,
                    "error": "llm_connection_failed",
                    "message": f"Cannot connect to LLM API: {message}",
                    "llm_profile": task_request.llm_profile_name
                }
        # Generate task ID
        task_id = uuid7str()

        # Get MCP server config for saving
        from ..shared_state import vibesurf_tools, active_mcp_server
        mcp_server_config = task_request.mcp_server_config
        if not mcp_server_config and vibesurf_tools and hasattr(vibesurf_tools, 'mcp_server_config'):
            mcp_server_config = vibesurf_tools.mcp_server_config

        # Ensure we have a valid MCP server config (never None)
        if mcp_server_config is None:
            mcp_server_config = {"mcpServers": {}}
            logger.info("Using default empty MCP server configuration")

        # DEBUG: Log the type and content of mcp_server_config
        logger.debug(f"mcp_server_config type: {type(mcp_server_config)}, value: {mcp_server_config}")

        # Create initial task record in database
        from ..database.queries import TaskQueries
        await TaskQueries.save_task(
            db,
            task_id=task_id,
            session_id=task_request.session_id,
            task_description=task_request.task_description,
            upload_files_path=task_request.upload_files_path,
            mcp_server_config=mcp_server_config,
            llm_profile_name=task_request.llm_profile_name,
            workspace_dir=workspace_dir,
            task_status="pending",
            agent_mode=task_request.agent_mode
        )
        await db.commit()

        # Add background task
        background_tasks.add_task(
            execute_task_background,
            task_id=task_id,
            session_id=task_request.session_id,
            task=task_request.task_description,
            llm_profile_name=task_request.llm_profile_name,
            upload_files=task_request.upload_files_path,
            agent_mode=task_request.agent_mode,
            db_session=db
        )

        return {
            "success": True,
            "task_id": task_id,
            "session_id": task_request.session_id,
            "status": "submitted",
            "message": "Task submitted for execution",
            "llm_profile": task_request.llm_profile_name,
            "workspace_dir": workspace_dir
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to submit task: {str(e)}")


async def _ensure_llm_initialized(llm_profile):
    """Ensure LLM is initialized with the specified profile and test connectivity"""
    from ..utils.llm_factory import create_llm_from_profile
    from ..shared_state import vibesurf_agent
    from browser_use.llm import UserMessage

    if not vibesurf_agent:
        raise HTTPException(status_code=503, detail="VibeSurf agent not initialized")

    try:
        # Always create new LLM instance to ensure we're using the right profile
        new_llm = create_llm_from_profile(llm_profile)

        # Test LLM connectivity with a simple question
        test_message = UserMessage(content='What is the capital of France? Answer in one word.')
        
        logger.info(f"Testing LLM connectivity for profile: {llm_profile['profile_name']}")
        response = await new_llm.ainvoke([test_message])
        
        # Check if response contains expected answer
        if not response or not hasattr(response, 'completion'):
            return False, f"LLM response validation failed: No completion content received"
        
        completion = response.completion.lower() if response.completion else ""
        if 'paris' not in completion:
            logger.warning(f"LLM connectivity test returned unexpected answer: {response.completion}")
            # Still continue if we got some response, just log the warning
        
        logger.info(f"LLM connectivity test successful for profile: {llm_profile['profile_name']}")

        # Update vibesurf agent's LLM and register with token cost service
        if vibesurf_agent and vibesurf_agent.token_cost_service:
            vibesurf_agent.llm = vibesurf_agent.token_cost_service.register_llm(new_llm)
            logger.info(f"LLM updated and registered for token tracking for profile: {llm_profile['profile_name']}")
        
        return True, "LLM initialized and tested successfully"
        
    except Exception as e:
        error_msg = f"LLM connectivity test failed: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


@router.post("/pause")
async def pause_task(control_request: TaskControlRequest):
    """Pause current task execution"""
    from ..shared_state import vibesurf_agent

    if not vibesurf_agent:
        raise HTTPException(status_code=503, detail="VibeSurf agent not initialized")

    if not is_task_running():
        raise HTTPException(status_code=400, detail="No active task to pause")

    try:
        result = await vibesurf_agent.pause(control_request.reason)

        if result.success:
            # Update active task status
            current_task = get_active_task_info()
            if current_task:
                from ..shared_state import active_task
                active_task["status"] = "paused"
                active_task["pause_reason"] = control_request.reason

            return {
                "success": True,
                "message": result.message,
                "operation": "pause"
            }
        else:
            raise HTTPException(status_code=500, detail=result.message)

    except Exception as e:
        logger.error(f"Failed to pause task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to pause task: {str(e)}")


@router.post("/resume")
async def resume_task(control_request: TaskControlRequest):
    """Resume current task execution"""
    from ..shared_state import vibesurf_agent

    if not vibesurf_agent:
        raise HTTPException(status_code=503, detail="VibeSurf agent not initialized")

    current_task = get_active_task_info()
    if not current_task or current_task.get("status") != "paused":
        raise HTTPException(status_code=400, detail="No paused task to resume")

    try:
        result = await vibesurf_agent.resume(control_request.reason)

        if result.success:
            # Update active task status
            from ..shared_state import active_task
            active_task["status"] = "running"
            active_task["resume_reason"] = control_request.reason

            return {
                "success": True,
                "message": result.message,
                "operation": "resume"
            }
        else:
            raise HTTPException(status_code=500, detail=result.message)

    except Exception as e:
        logger.error(f"Failed to resume task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to resume task: {str(e)}")


@router.post("/stop")
async def stop_task(control_request: TaskControlRequest):
    """Stop current task execution"""
    from ..shared_state import vibesurf_agent

    if not vibesurf_agent:
        raise HTTPException(status_code=503, detail="VibeSurf agent not initialized")

    if not is_task_running():
        raise HTTPException(status_code=400, detail="No active task to stop")

    try:
        result = await vibesurf_agent.stop(control_request.reason)

        if result.success:
            # Update active task status and clear it
            current_task = get_active_task_info()
            if current_task:
                from ..shared_state import active_task
                active_task["status"] = "stopped"
                active_task["stop_reason"] = control_request.reason
                active_task["end_time"] = datetime.now()

            # Clear active task
            clear_active_task()

            return {
                "success": True,
                "message": result.message,
                "operation": "stop"
            }
        else:
            raise HTTPException(status_code=500, detail=result.message)

    except Exception as e:
        logger.error(f"Failed to stop task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop task: {str(e)}")


@router.post("/add-new-task")
async def add_new_task(control_request: TaskControlRequest):
    """Add a new task or follow-up instruction during execution"""
    from ..shared_state import vibesurf_agent

    if not vibesurf_agent:
        raise HTTPException(status_code=503, detail="VibeSurf agent not initialized")

    if not is_task_running():
        raise HTTPException(status_code=400, detail="No active task to add new instruction to")

    try:
        # Use the reason field as the new task content
        new_task = control_request.reason or "No additional task provided"
        
        # Add the new task to the running agent
        await vibesurf_agent.add_new_task(new_task)

        return {
            "success": True,
            "message": "New task added successfully",
            "operation": "add_new_task",
            "new_task": new_task
        }

    except Exception as e:
        logger.error(f"Failed to add new task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add new task: {str(e)}")


@router.get("/detailed-status")
async def get_detailed_task_status():
    """Get detailed task execution status with vibesurf information"""
    from ..shared_state import vibesurf_agent

    if not vibesurf_agent:
        raise HTTPException(status_code=503, detail="VibeSurf agent not initialized")

    try:
        current_task = get_active_task_info()

        if current_task:
            # Get detailed vibesurf status
            vibesurf_status = vibesurf_agent.get_status()

            return {
                "has_active_task": True,
                "task_id": current_task["task_id"],
                "status": current_task["status"],
                "session_id": current_task["session_id"],
                "task": current_task["task"],
                "start_time": current_task["start_time"].isoformat() if current_task.get("start_time") else None,
                "end_time": current_task.get("end_time").isoformat() if current_task.get("end_time") else None,
                "result": current_task.get("result"),
                "error": current_task.get("error"),
                "pause_reason": current_task.get("pause_reason"),
                "stop_reason": current_task.get("stop_reason"),
                "vibesurf_status": {
                    "overall_status": vibesurf_status.overall_status,
                    "active_step": vibesurf_status.active_step,
                    "agent_statuses": {k: v.dict() for k, v in vibesurf_status.agent_statuses.items()},
                    "progress": vibesurf_status.progress,
                    "last_update": vibesurf_status.last_update.isoformat()
                }
            }
        else:
            return {
                "has_active_task": False,
                "message": "No active task"
            }

    except Exception as e:
        logger.error(f"Failed to get task status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(e)}")
