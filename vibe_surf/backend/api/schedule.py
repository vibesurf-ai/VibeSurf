"""
Schedule API endpoints for managing workflow schedules
"""

import asyncio
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from croniter import croniter
from sqlalchemy import text

from vibe_surf.backend.database.models import Schedule
from vibe_surf.backend.database.queries import ScheduleQueries
from vibe_surf.backend.database.manager import get_db_session
from vibe_surf.backend import shared_state
from vibe_surf.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/schedule", tags=["schedule"])

# Pydantic models for request/response
class ScheduleCreate(BaseModel):
    flow_id: str = Field(..., description="Flow ID to schedule")
    cron_expression: Optional[str] = Field(None, description="Cron expression (e.g., '0 9 * * 1-5')")
    is_enabled: bool = Field(True, description="Whether the schedule is enabled")
    description: Optional[str] = Field(None, description="Optional description for the schedule")

class ScheduleUpdate(BaseModel):
    cron_expression: Optional[str] = Field(None, description="Cron expression (e.g., '0 9 * * 1-5')")
    is_enabled: Optional[bool] = Field(None, description="Whether the schedule is enabled")
    description: Optional[str] = Field(None, description="Optional description for the schedule")

class ScheduleResponse(BaseModel):
    id: str
    flow_id: str
    cron_expression: Optional[str]
    is_enabled: bool
    description: Optional[str]
    last_execution_at: Optional[datetime]
    next_execution_at: Optional[datetime]
    execution_count: int
    created_at: datetime
    updated_at: datetime

def validate_cron_expression(cron_expr: str) -> bool:
    """Validate cron expression format"""
    try:
        croniter(cron_expr)
        return True
    except (ValueError, TypeError):
        return False

def calculate_next_execution(cron_expr: str) -> Optional[datetime]:
    """Calculate next execution time from cron expression"""
    if not cron_expr:
        return None
    try:
        # Use system local timezone for cron calculation, then convert to UTC for storage
        local_now = datetime.now().astimezone()
        cron = croniter(cron_expr, local_now)
        local_next = cron.get_next(datetime)
        # Make sure the result has timezone info
        if local_next.tzinfo is None:
            local_next = local_next.replace(tzinfo=local_now.tzinfo)
        # Convert to UTC for consistent storage
        return local_next.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None

@router.get("", response_model=List[ScheduleResponse])
async def get_schedules(db: AsyncSession = Depends(get_db_session)):
    """Get all schedules"""
    try:
        schedules = await ScheduleQueries.list_schedules(db)
        
        schedule_list = []
        for schedule in schedules:
            schedule_dict = {
                "id": schedule.id,
                "flow_id": schedule.flow_id,
                "cron_expression": schedule.cron_expression,
                "is_enabled": schedule.is_enabled,
                "description": schedule.description,
                "last_execution_at": schedule.last_execution_at,
                "next_execution_at": schedule.next_execution_at,
                "execution_count": schedule.execution_count,
                "created_at": schedule.created_at,
                "updated_at": schedule.updated_at
            }
            schedule_list.append(ScheduleResponse(**schedule_dict))
        
        return schedule_list

    except Exception as e:
        logger.error(f"Error getting schedules: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get schedules: {str(e)}"
        )

@router.post("", response_model=ScheduleResponse)
async def create_schedule(schedule_data: ScheduleCreate, db: AsyncSession = Depends(get_db_session)):
    """Create a new schedule"""
    try:
        from vibe_surf.backend.shared_state import schedule_manager

        # Validate cron expression if provided
        if schedule_data.cron_expression and not validate_cron_expression(schedule_data.cron_expression):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cron expression format"
            )

        # Check if schedule already exists for this flow
        existing_schedule = await ScheduleQueries.get_schedule_by_flow_id(db, schedule_data.flow_id)
        if existing_schedule:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Schedule already exists for flow {schedule_data.flow_id}"
            )

        # Create new schedule
        schedule_data_dict = await ScheduleQueries.create_schedule(
            db=db,
            flow_id=schedule_data.flow_id,
            cron_expression=schedule_data.cron_expression,
            is_enabled=schedule_data.is_enabled,
            description=schedule_data.description
        )

        # Commit the transaction
        await db.commit()

        # Update the schedule manager if available
        if schedule_manager:
            await schedule_manager.reload_schedules()
        else:
            logger.warning("[ScheduleAPI] Schedule manager not available for reload")

        logger.info(f"[ScheduleAPI] Successfully created schedule for flow {schedule_data.flow_id}")
        return ScheduleResponse(**schedule_data_dict)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating schedule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create schedule: {str(e)}"
        )

@router.get("/{flow_id}", response_model=ScheduleResponse)
async def get_schedule(flow_id: str, db: AsyncSession = Depends(get_db_session)):
    """Get a specific schedule by flow ID"""
    try:
        schedule = await ScheduleQueries.get_schedule_by_flow_id(db, flow_id)
        
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schedule not found for flow {flow_id}"
            )

        schedule_dict = {
            "id": schedule.id,
            "flow_id": schedule.flow_id,
            "cron_expression": schedule.cron_expression,
            "is_enabled": schedule.is_enabled,
            "description": schedule.description,
            "last_execution_at": schedule.last_execution_at,
            "next_execution_at": schedule.next_execution_at,
            "execution_count": schedule.execution_count,
            "created_at": schedule.created_at,
            "updated_at": schedule.updated_at
        }
        
        return ScheduleResponse(**schedule_dict)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting schedule for flow {flow_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get schedule: {str(e)}"
        )

@router.put("/{flow_id}", response_model=ScheduleResponse)
async def update_schedule(flow_id: str, schedule_data: ScheduleUpdate, db: AsyncSession = Depends(get_db_session)):
    """Update an existing schedule by flow ID"""
    try:
        from vibe_surf.backend.shared_state import schedule_manager

        # Validate cron expression if provided
        if schedule_data.cron_expression is not None and not validate_cron_expression(schedule_data.cron_expression):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cron expression format"
            )

        # Prepare update data
        updates = {}
        if schedule_data.cron_expression is not None:
            updates["cron_expression"] = schedule_data.cron_expression
        if schedule_data.is_enabled is not None:
            updates["is_enabled"] = schedule_data.is_enabled
        if schedule_data.description is not None:
            updates["description"] = schedule_data.description

        if not updates:
            # No fields to update, return existing schedule
            schedule = await ScheduleQueries.get_schedule_by_flow_id(db, flow_id)
            if not schedule:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Schedule not found for flow {flow_id}"
                )
            
            schedule_dict = {
                "id": schedule.id,
                "flow_id": schedule.flow_id,
                "cron_expression": schedule.cron_expression,
                "is_enabled": schedule.is_enabled,
                "description": schedule.description,
                "last_execution_at": schedule.last_execution_at,
                "next_execution_at": schedule.next_execution_at,
                "execution_count": schedule.execution_count,
                "created_at": schedule.created_at,
                "updated_at": schedule.updated_at
            }
            return ScheduleResponse(**schedule_dict)

        # Update schedule by flow_id
        success = await ScheduleQueries.update_schedule_by_flow_id(db, flow_id, updates)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schedule not found for flow {flow_id}"
            )

        # Commit the transaction
        await db.commit()

        # Fetch updated schedule
        updated_schedule = await ScheduleQueries.get_schedule_by_flow_id(db, flow_id)
        
        if not updated_schedule:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update schedule"
            )

        schedule_dict = {
            "id": updated_schedule.id,
            "flow_id": updated_schedule.flow_id,
            "cron_expression": updated_schedule.cron_expression,
            "is_enabled": updated_schedule.is_enabled,
            "description": updated_schedule.description,
            "last_execution_at": updated_schedule.last_execution_at,
            "next_execution_at": updated_schedule.next_execution_at,
            "execution_count": updated_schedule.execution_count,
            "created_at": updated_schedule.created_at,
            "updated_at": updated_schedule.updated_at
        }

        # Update the schedule manager if available
        if schedule_manager:
            await schedule_manager.reload_schedules()

        logger.info(f"Updated schedule for flow {flow_id}")
        return ScheduleResponse(**schedule_dict)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating schedule for flow {flow_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update schedule: {str(e)}"
        )

@router.delete("/{flow_id}")
async def delete_schedule(flow_id: str, db: AsyncSession = Depends(get_db_session)):
    """Delete a schedule by flow ID"""
    try:
        from vibe_surf.backend.shared_state import schedule_manager

        # Check if schedule exists
        existing_schedule = await ScheduleQueries.get_schedule_by_flow_id(db, flow_id)
        
        if not existing_schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schedule not found for flow {flow_id}"
            )

        # Delete schedule
        success = await ScheduleQueries.delete_schedule_by_flow_id(db, flow_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete schedule"
            )

        # Commit the transaction
        await db.commit()

        # Update the schedule manager if available
        if schedule_manager:
            await schedule_manager.reload_schedules()

        logger.info(f"Deleted schedule for flow {flow_id}")
        return {"message": f"Schedule deleted for flow {flow_id}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting schedule for flow {flow_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete schedule: {str(e)}"
        )