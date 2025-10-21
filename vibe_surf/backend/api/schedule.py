"""
Schedule API endpoints for managing workflow schedules
"""

import asyncio
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from croniter import croniter

from vibe_surf.backend.database.models import Schedule
from vibe_surf.backend import shared_state
from vibe_surf.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

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
        cron = croniter(cron_expr, datetime.now(timezone.utc))
        return cron.get_next(datetime)
    except (ValueError, TypeError):
        return None

@router.get("/", response_model=List[ScheduleResponse])
async def get_schedules():
    """Get all schedules"""
    try:
        if not shared_state.db_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )

        async for session in shared_state.db_manager.get_session():
            result = await session.execute("SELECT * FROM schedules ORDER BY created_at DESC")
            schedules = result.fetchall()
            
            schedule_list = []
            for row in schedules:
                schedule_dict = dict(row._mapping) if hasattr(row, '_mapping') else dict(row)
                schedule_list.append(ScheduleResponse(**schedule_dict))
            
            return schedule_list

    except Exception as e:
        logger.error(f"Error getting schedules: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get schedules: {str(e)}"
        )

@router.post("/", response_model=ScheduleResponse)
async def create_schedule(schedule_data: ScheduleCreate):
    """Create a new schedule"""
    try:
        if not shared_state.db_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )

        # Validate cron expression if provided
        if schedule_data.cron_expression and not validate_cron_expression(schedule_data.cron_expression):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cron expression format"
            )

        # Calculate next execution time
        next_execution = calculate_next_execution(schedule_data.cron_expression) if schedule_data.cron_expression else None

        schedule_id = str(uuid4())
        now = datetime.now(timezone.utc)

        async for session in shared_state.db_manager.get_session():
            # Check if schedule already exists for this flow
            result = await session.execute(
                "SELECT id FROM schedules WHERE flow_id = ?",
                (schedule_data.flow_id,)
            )
            existing = result.fetchone()
            
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Schedule already exists for flow {schedule_data.flow_id}"
                )

            # Insert new schedule
            await session.execute("""
                INSERT INTO schedules (
                    id, flow_id, cron_expression, is_enabled, description,
                    next_execution_at, execution_count, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                schedule_id,
                schedule_data.flow_id,
                schedule_data.cron_expression,
                schedule_data.is_enabled,
                schedule_data.description,
                next_execution,
                0,
                now,
                now
            ))

            await session.commit()

            # Fetch the created schedule
            result = await session.execute(
                "SELECT * FROM schedules WHERE id = ?",
                (schedule_id,)
            )
            schedule_row = result.fetchone()
            
            if not schedule_row:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create schedule"
                )

            schedule_dict = dict(schedule_row._mapping) if hasattr(schedule_row, '_mapping') else dict(schedule_row)
            created_schedule = ScheduleResponse(**schedule_dict)

            # Update the schedule manager if available
            if hasattr(shared_state, 'schedule_manager') and shared_state.schedule_manager:
                await shared_state.schedule_manager.reload_schedules()

            logger.info(f"Created schedule for flow {schedule_data.flow_id}")
            return created_schedule

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating schedule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create schedule: {str(e)}"
        )

@router.get("/{flow_id}", response_model=ScheduleResponse)
async def get_schedule(flow_id: str):
    """Get a specific schedule by flow ID"""
    try:
        if not shared_state.db_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )

        async for session in shared_state.db_manager.get_session():
            result = await session.execute(
                "SELECT * FROM schedules WHERE flow_id = ?",
                (flow_id,)
            )
            schedule_row = result.fetchone()
            
            if not schedule_row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Schedule not found for flow {flow_id}"
                )

            schedule_dict = dict(schedule_row._mapping) if hasattr(schedule_row, '_mapping') else dict(schedule_row)
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
async def update_schedule(flow_id: str, schedule_data: ScheduleUpdate):
    """Update an existing schedule"""
    try:
        if not shared_state.db_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )

        # Validate cron expression if provided
        if schedule_data.cron_expression is not None and not validate_cron_expression(schedule_data.cron_expression):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cron expression format"
            )

        async for session in shared_state.db_manager.get_session():
            # Check if schedule exists
            result = await session.execute(
                "SELECT * FROM schedules WHERE flow_id = ?",
                (flow_id,)
            )
            existing_schedule = result.fetchone()
            
            if not existing_schedule:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Schedule not found for flow {flow_id}"
                )

            # Prepare update data
            update_fields = []
            update_values = []
            
            if schedule_data.cron_expression is not None:
                update_fields.append("cron_expression = ?")
                update_values.append(schedule_data.cron_expression)
                
                # Calculate new next execution time
                next_execution = calculate_next_execution(schedule_data.cron_expression)
                update_fields.append("next_execution_at = ?")
                update_values.append(next_execution)
            
            if schedule_data.is_enabled is not None:
                update_fields.append("is_enabled = ?")
                update_values.append(schedule_data.is_enabled)
            
            if schedule_data.description is not None:
                update_fields.append("description = ?")
                update_values.append(schedule_data.description)
            
            if not update_fields:
                # No fields to update, return existing schedule
                schedule_dict = dict(existing_schedule._mapping) if hasattr(existing_schedule, '_mapping') else dict(existing_schedule)
                return ScheduleResponse(**schedule_dict)

            # Add updated_at
            update_fields.append("updated_at = ?")
            update_values.append(datetime.now(timezone.utc))
            
            # Add flow_id for WHERE clause
            update_values.append(flow_id)

            # Execute update
            await session.execute(
                f"UPDATE schedules SET {', '.join(update_fields)} WHERE flow_id = ?",
                update_values
            )
            
            await session.commit()

            # Fetch updated schedule
            result = await session.execute(
                "SELECT * FROM schedules WHERE flow_id = ?",
                (flow_id,)
            )
            updated_schedule = result.fetchone()
            
            if not updated_schedule:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update schedule"
                )

            schedule_dict = dict(updated_schedule._mapping) if hasattr(updated_schedule, '_mapping') else dict(updated_schedule)
            result_schedule = ScheduleResponse(**schedule_dict)

            # Update the schedule manager if available
            if hasattr(shared_state, 'schedule_manager') and shared_state.schedule_manager:
                await shared_state.schedule_manager.reload_schedules()

            logger.info(f"Updated schedule for flow {flow_id}")
            return result_schedule

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating schedule for flow {flow_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update schedule: {str(e)}"
        )

@router.delete("/{flow_id}")
async def delete_schedule(flow_id: str):
    """Delete a schedule"""
    try:
        if not shared_state.db_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )

        async for session in shared_state.db_manager.get_session():
            # Check if schedule exists
            result = await session.execute(
                "SELECT id FROM schedules WHERE flow_id = ?",
                (flow_id,)
            )
            existing_schedule = result.fetchone()
            
            if not existing_schedule:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Schedule not found for flow {flow_id}"
                )

            # Delete schedule
            await session.execute(
                "DELETE FROM schedules WHERE flow_id = ?",
                (flow_id,)
            )
            
            await session.commit()

            # Update the schedule manager if available
            if hasattr(shared_state, 'schedule_manager') and shared_state.schedule_manager:
                await shared_state.schedule_manager.reload_schedules()

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