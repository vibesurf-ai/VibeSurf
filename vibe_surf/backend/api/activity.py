"""
Activity Logs Router - Simplified

Handles retrieval of activity logs from VibeSurf agents and task history from database.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import logging
from datetime import datetime

from ..database import get_db_session
from ..database.queries import TaskQueries
from .models import ActivityQueryRequest, SessionActivityQueryRequest

from vibe_surf.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/activity", tags=["activity"])

# Task History Endpoints

@router.get("/tasks")
async def get_recent_tasks(
    limit: int = -1,
    db: AsyncSession = Depends(get_db_session)
):
    """Get recent tasks across all sessions"""
    try:
        # Handle -1 as "get all" and validate other values
        if limit != -1 and (limit < 1 or limit > 1000):
            limit = -1
            
        tasks = await TaskQueries.get_recent_tasks(db, limit)
        
        return {
            "tasks": [
                {
                    "task_id": task.task_id,
                    "session_id": task.session_id,
                    "task_description": task.task_description,
                    "status": task.status.value,
                    "task_result": task.task_result,
                    "error_message": task.error_message,
                    "report_path": task.report_path,
                    "created_at": task.created_at.isoformat(),
                    "started_at": task.started_at.isoformat() if task.started_at else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None
                }
                for task in tasks
            ],
            "total_count": len(tasks),
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Failed to get recent tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recent tasks: {str(e)}")

@router.get("/sessions")
async def get_all_sessions(
    limit: int = -1,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_session)
):
    """Get all sessions with task counts and metadata"""
    try:
        # Handle -1 as "get all" and validate other values
        if limit != -1 and (limit < 1 or limit > 1000):
            limit = -1
            
        sessions = await TaskQueries.get_all_sessions(db, limit, offset)
        
        return {
            "sessions": sessions,
            "total_count": len(sessions),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Failed to get all sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get all sessions: {str(e)}")

@router.get("/sessions/{session_id}/tasks")
async def get_session_tasks(
    session_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Get all tasks for a session from database"""
    try:
        tasks = await TaskQueries.get_tasks_by_session(db, session_id)
        
        return {
            "session_id": session_id,
            "tasks": [
                {
                    "task_id": task.task_id,
                    "task_description": task.task_description,
                    "status": task.status.value,
                    "task_result": task.task_result,
                    "llm_profile_name": task.llm_profile_name,
                    "workspace_dir": task.workspace_dir,
                    "mcp_server_config": task.mcp_server_config,
                    "error_message": task.error_message,
                    "report_path": task.report_path,
                    "created_at": task.created_at.isoformat(),
                    "started_at": task.started_at.isoformat() if task.started_at else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None
                }
                for task in tasks
            ],
            "total_count": len(tasks)
        }
    except Exception as e:
        logger.error(f"Failed to get tasks for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get session tasks: {str(e)}")

@router.get("/{task_id}")
async def get_task_info(
    task_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Get task information and result from database"""
    try:
        task = await TaskQueries.get_task(db, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return {
            "task_id": task.task_id,
            "session_id": task.session_id,
            "task_description": task.task_description,
            "status": task.status.value,
            "upload_files_path": task.upload_files_path,
            "mcp_server_config": task.mcp_server_config,
            "llm_profile_name": task.llm_profile_name,
            "task_result": task.task_result,
            "error_message": task.error_message,
            "report_path": task.report_path,
            "created_at": task.created_at.isoformat(),
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "metadata": task.task_metadata
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task info for {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get task info: {str(e)}")

# Real-time VibeSurf Agent Activity Log Endpoints

@router.get("/sessions/{session_id}/activity")
async def get_session_activity_logs(
    session_id: str,
    query: SessionActivityQueryRequest = Depends()
):
    """Get real-time VibeSurf agent activity logs for a specific session"""
    from ..shared_state import vibesurf_agent
    
    if not vibesurf_agent:
        logger.error(f"❌ VibeSurf agent not initialized")
        raise HTTPException(status_code=503, detail="VibeSurf agent not initialized")
    
    try:
        # Get activity logs from VibeSurfAgent
        if query.message_index is not None:
            # First get all logs to check the current state
            all_logs = vibesurf_agent.get_activity_logs(session_id)
            
            # Get specific log entry by index
            activity_log = vibesurf_agent.get_activity_logs(session_id, query.message_index)
            
            if activity_log is None:
                return {
                    "session_id": session_id,
                    "activity_log": None,
                    "message_index": query.message_index,
                    "total_available": len(all_logs) if all_logs else 0,
                    "message": f"No activity log found at index {query.message_index}"
                }
            
            return {
                "session_id": session_id,
                "activity_log": activity_log,
                "message_index": query.message_index,
                "total_available": len(all_logs) if all_logs else 0
            }
        else:
            # Get all activity logs for the session
            activity_logs = vibesurf_agent.get_activity_logs(session_id)
            
            if activity_logs is None:
                return {
                    "session_id": session_id,
                    "activity_logs": [],
                    "total_count": 0,
                    "message": "No activity logs found for this session"
                }
            
            # Apply limit (-1 means no limit)
            original_count = len(activity_logs)
            if query.limit != -1 and query.limit > 0 and len(activity_logs) > query.limit:
                activity_logs = activity_logs[-query.limit:]
            
            return {
                "session_id": session_id,
                "activity_logs": activity_logs,
                "total_count": len(activity_logs),
                "original_total": original_count
            }
        
    except Exception as e:
        logger.error(f"❌ Failed to get VibeSurf activity logs for session {session_id}: {e}")
        logger.exception("Full traceback:")
        raise HTTPException(status_code=500, detail=f"Failed to get activity logs: {str(e)}")


@router.get("/sessions/{session_id}/latest_activity")
async def get_latest_activity(session_id: str):
    """Get the latest activity for a session (both task info and VibeSurf logs)"""
    
    try:
        from ..shared_state import vibesurf_agent
        result = {
            "session_id": session_id,
            "latest_vibesurf_log": None,
            "latest_task": None
        }
        
        # Get latest VibeSurf activity log
        if vibesurf_agent:
            try:
                activity_logs = vibesurf_agent.get_activity_logs(session_id)
                if activity_logs:
                    result["latest_vibesurf_log"] = activity_logs[-1]
            except Exception as e:
                logger.warning(f"Failed to get VibeSurf activity for {session_id}: {e}")
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get latest activity for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get latest activity: {str(e)}")
