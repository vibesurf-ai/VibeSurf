"""
Database Query Operations for VibeSurf Backend - With LLM Profile Management

Centralized database operations for Task and LLMProfile tables.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, desc, and_, or_
from sqlalchemy.orm import selectinload
from .models import Task, TaskStatus, LLMProfile, UploadedFile, McpProfile, VoiceProfile, VoiceModelType
from ..utils.encryption import encrypt_api_key, decrypt_api_key
import logging
import json

from vibe_surf.logger import get_logger

logger = get_logger(__name__)


class LLMProfileQueries:
    """Query operations for LLMProfile model"""

    @staticmethod
    async def create_profile(
            db: AsyncSession,
            profile_name: str,
            provider: str,
            model: str,
            api_key: Optional[str] = None,
            base_url: Optional[str] = None,
            temperature: Optional[float] = None,
            max_tokens: Optional[int] = None,
            top_p: Optional[float] = None,
            frequency_penalty: Optional[float] = None,
            seed: Optional[int] = None,
            provider_config: Optional[Dict[str, Any]] = None,
            description: Optional[str] = None,
            is_default: bool = False
    ) -> Dict[str, Any]:
        """Create a new LLM profile with encrypted API key"""
        try:
            # Encrypt API key if provided
            encrypted_api_key = encrypt_api_key(api_key) if api_key else None

            profile = LLMProfile(
                profile_name=profile_name,
                provider=provider,
                model=model,
                base_url=base_url,
                encrypted_api_key=encrypted_api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                seed=seed,
                provider_config=provider_config or {},
                description=description,
                is_default=is_default
            )

            db.add(profile)
            await db.flush()
            await db.refresh(profile)

            # Extract data immediately to avoid greenlet issues
            profile_data = {
                "profile_id": profile.profile_id,
                "profile_name": profile.profile_name,
                "provider": profile.provider,
                "model": profile.model,
                "base_url": profile.base_url,
                "temperature": profile.temperature,
                "max_tokens": profile.max_tokens,
                "top_p": profile.top_p,
                "frequency_penalty": profile.frequency_penalty,
                "seed": profile.seed,
                "provider_config": profile.provider_config,
                "description": profile.description,
                "is_active": profile.is_active,
                "is_default": profile.is_default,
                "created_at": profile.created_at,
                "updated_at": profile.updated_at,
                "last_used_at": profile.last_used_at
            }

            return profile_data
        except Exception as e:
            logger.error(f"Failed to create LLM profile {profile_name}: {e}")
            raise

    @staticmethod
    async def get_profile(db: AsyncSession, profile_name: str) -> Optional[LLMProfile]:
        """Get LLM profile by name"""
        try:
            result = await db.execute(
                select(LLMProfile).where(LLMProfile.profile_name == profile_name)
            )
            profile = result.scalar_one_or_none()
            if profile:
                # Ensure all attributes are loaded by accessing them
                _ = (profile.profile_id, profile.created_at, profile.updated_at,
                     profile.last_used_at, profile.is_active, profile.is_default)
            return profile
        except Exception as e:
            logger.error(f"Failed to get LLM profile {profile_name}: {e}")
            raise

    @staticmethod
    async def get_profile_with_decrypted_key(db: AsyncSession, profile_name: str) -> Optional[Dict[str, Any]]:
        """Get LLM profile with decrypted API key"""
        try:
            profile = await LLMProfileQueries.get_profile(db, profile_name)
            if not profile:
                return None

            # Decrypt API key
            decrypted_api_key = decrypt_api_key(profile.encrypted_api_key) if profile.encrypted_api_key else None

            return {
                "profile_id": profile.profile_id,
                "profile_name": profile.profile_name,
                "provider": profile.provider,
                "model": profile.model,
                "base_url": profile.base_url,
                "api_key": decrypted_api_key,  # Decrypted for use
                "temperature": profile.temperature,
                "max_tokens": profile.max_tokens,
                "top_p": profile.top_p,
                "frequency_penalty": profile.frequency_penalty,
                "seed": profile.seed,
                "provider_config": profile.provider_config,
                "description": profile.description,
                "is_active": profile.is_active,
                "is_default": profile.is_default,
                "created_at": profile.created_at,
                "updated_at": profile.updated_at,
                "last_used_at": profile.last_used_at
            }
        except Exception as e:
            logger.error(f"Failed to get LLM profile with decrypted key {profile_name}: {e}")
            raise

    @staticmethod
    async def list_profiles(
            db: AsyncSession,
            active_only: bool = True,
            limit: int = 50,
            offset: int = 0
    ) -> List[LLMProfile]:
        """List LLM profiles"""
        try:
            query = select(LLMProfile)

            if active_only:
                query = query.where(LLMProfile.is_active == True)

            query = query.order_by(desc(LLMProfile.last_used_at), desc(LLMProfile.created_at))
            query = query.limit(limit).offset(offset)

            result = await db.execute(query)
            profiles = result.scalars().all()

            # Ensure all attributes are loaded for each profile
            for profile in profiles:
                _ = (profile.profile_id, profile.created_at, profile.updated_at,
                     profile.last_used_at, profile.is_active, profile.is_default)

            return profiles
        except Exception as e:
            logger.error(f"Failed to list LLM profiles: {e}")
            raise

    @staticmethod
    async def update_profile(
            db: AsyncSession,
            profile_name: str,
            updates: Dict[str, Any]
    ) -> bool:
        """Update LLM profile"""
        try:
            # Handle API key encryption if present
            if "api_key" in updates:
                api_key = updates.pop("api_key")
                if api_key:
                    updates["encrypted_api_key"] = encrypt_api_key(api_key)
                else:
                    updates["encrypted_api_key"] = None

            result = await db.execute(
                update(LLMProfile)
                .where(LLMProfile.profile_name == profile_name)
                .values(**updates)
            )

            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update LLM profile {profile_name}: {e}")
            raise

    @staticmethod
    async def delete_profile(db: AsyncSession, profile_name: str) -> bool:
        """Delete LLM profile"""
        try:
            result = await db.execute(
                delete(LLMProfile).where(LLMProfile.profile_name == profile_name)
            )
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to delete LLM profile {profile_name}: {e}")
            raise

    @staticmethod
    async def get_default_profile(db: AsyncSession) -> Optional[LLMProfile]:
        """Get the default LLM profile"""
        try:
            result = await db.execute(
                select(LLMProfile).where(LLMProfile.is_default == True)
            )
            profile = result.scalar_one_or_none()
            if profile:
                # Ensure all attributes are loaded by accessing them
                _ = (profile.profile_id, profile.created_at, profile.updated_at,
                     profile.last_used_at, profile.is_active, profile.is_default)
            return profile
        except Exception as e:
            logger.error(f"Failed to get default LLM profile: {e}")
            raise

    @staticmethod
    async def set_default_profile(db: AsyncSession, profile_name: str) -> bool:
        """Set a profile as default (and unset others)"""
        try:
            # First, unset all defaults
            await db.execute(
                update(LLMProfile).values(is_default=False)
            )

            # Then set the specified profile as default
            result = await db.execute(
                update(LLMProfile)
                .where(LLMProfile.profile_name == profile_name)
                .values(is_default=True)
            )

            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to set default LLM profile {profile_name}: {e}")
            raise

    @staticmethod
    async def update_last_used(db: AsyncSession, profile_name: str) -> bool:
        """Update the last_used_at timestamp for a profile"""
        try:
            result = await db.execute(
                update(LLMProfile)
                .where(LLMProfile.profile_name == profile_name)
                .values(last_used_at=func.now())
            )
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update last_used for LLM profile {profile_name}: {e}")
            raise


class McpProfileQueries:
    """Query operations for McpProfile model"""

    @staticmethod
    async def create_profile(
            db: AsyncSession,
            display_name: str,
            mcp_server_name: str,
            mcp_server_params: Dict[str, Any],
            description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new MCP profile"""
        try:
            profile = McpProfile(
                display_name=display_name,
                mcp_server_name=mcp_server_name,
                mcp_server_params=mcp_server_params,
                description=description
            )

            db.add(profile)
            await db.flush()
            await db.refresh(profile)

            # Extract data immediately to avoid greenlet issues
            profile_data = {
                "mcp_id": profile.mcp_id,
                "display_name": profile.display_name,
                "mcp_server_name": profile.mcp_server_name,
                "mcp_server_params": profile.mcp_server_params,
                "description": profile.description,
                "is_active": profile.is_active,
                "created_at": profile.created_at,
                "updated_at": profile.updated_at,
                "last_used_at": profile.last_used_at
            }

            return profile_data
        except Exception as e:
            logger.error(f"Failed to create MCP profile {display_name}: {e}")
            raise

    @staticmethod
    async def get_profile(db: AsyncSession, mcp_id: str) -> Optional[McpProfile]:
        """Get MCP profile by ID"""
        try:
            result = await db.execute(
                select(McpProfile).where(McpProfile.mcp_id == mcp_id)
            )
            profile = result.scalar_one_or_none()
            if profile:
                # Ensure all attributes are loaded by accessing them
                _ = (profile.mcp_id, profile.created_at, profile.updated_at,
                     profile.last_used_at, profile.is_active)
            return profile
        except Exception as e:
            logger.error(f"Failed to get MCP profile {mcp_id}: {e}")
            raise

    @staticmethod
    async def get_profile_by_display_name(db: AsyncSession, display_name: str) -> Optional[McpProfile]:
        """Get MCP profile by display name"""
        try:
            result = await db.execute(
                select(McpProfile).where(McpProfile.display_name == display_name)
            )
            profile = result.scalar_one_or_none()
            if profile:
                _ = (profile.mcp_id, profile.created_at, profile.updated_at,
                     profile.last_used_at, profile.is_active)
            return profile
        except Exception as e:
            logger.error(f"Failed to get MCP profile by display name {display_name}: {e}")
            raise

    @staticmethod
    async def list_profiles(
            db: AsyncSession,
            active_only: bool = True,
            limit: int = 50,
            offset: int = 0
    ) -> List[McpProfile]:
        """List MCP profiles"""
        try:
            query = select(McpProfile)

            if active_only:
                query = query.where(McpProfile.is_active == True)

            query = query.order_by(desc(McpProfile.last_used_at), desc(McpProfile.created_at))
            query = query.limit(limit).offset(offset)

            result = await db.execute(query)
            profiles = result.scalars().all()

            # Ensure all attributes are loaded for each profile
            for profile in profiles:
                _ = (profile.mcp_id, profile.created_at, profile.updated_at,
                     profile.last_used_at, profile.is_active)

            return profiles
        except Exception as e:
            logger.error(f"Failed to list MCP profiles: {e}")
            raise

    @staticmethod
    async def get_active_profiles(db: AsyncSession) -> List[McpProfile]:
        """Get all active MCP profiles"""
        try:
            result = await db.execute(
                select(McpProfile).where(McpProfile.is_active == True)
            )
            profiles = result.scalars().all()

            # Ensure all attributes are loaded for each profile
            for profile in profiles:
                _ = (profile.mcp_id, profile.created_at, profile.updated_at,
                     profile.last_used_at, profile.is_active)

            return profiles
        except Exception as e:
            logger.error(f"Failed to get active MCP profiles: {e}")
            raise

    @staticmethod
    async def update_profile(
            db: AsyncSession,
            mcp_id: str,
            updates: Dict[str, Any]
    ) -> bool:
        """Update MCP profile"""
        try:
            logger.info(f"Updating profile {mcp_id}")

            result = await db.execute(
                update(McpProfile)
                .where(McpProfile.mcp_id == mcp_id)
                .values(**updates)
            )

            rows_affected = result.rowcount
            logger.info(f"Update query affected {rows_affected} rows")

            return rows_affected > 0
        except Exception as e:
            logger.error(f"Failed to update MCP profile {mcp_id}: {e}")
            raise

    @staticmethod
    async def delete_profile(db: AsyncSession, mcp_id: str) -> bool:
        """Delete MCP profile"""
        try:
            result = await db.execute(
                delete(McpProfile).where(McpProfile.mcp_id == mcp_id)
            )
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to delete MCP profile {mcp_id}: {e}")
            raise

    @staticmethod
    async def update_last_used(db: AsyncSession, mcp_id: str) -> bool:
        """Update the last_used_at timestamp for a profile"""
        try:
            result = await db.execute(
                update(McpProfile)
                .where(McpProfile.mcp_id == mcp_id)
                .values(last_used_at=func.now())
            )
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update last_used for MCP profile {mcp_id}: {e}")
            raise


class TaskQueries:
    """Database queries for task management with LLM Profile support"""

    @staticmethod
    async def save_task(
            db: AsyncSession,
            task_id: str,
            session_id: str,
            task_description: str,
            llm_profile_name: str,
            upload_files_path: Optional[str] = None,
            workspace_dir: Optional[str] = None,
            mcp_server_config: Optional[str] = None,  # JSON string
            task_result: Optional[str] = None,
            task_status: str = "pending",
            error_message: Optional[str] = None,
            report_path: Optional[str] = None,
            agent_mode: str = "thinking"
    ) -> Task:
        """Create or update a task record"""
        try:
            # Check if task exists
            result = await db.execute(select(Task).where(Task.task_id == task_id))
            existing_task = result.scalar_one_or_none()

            if existing_task:
                # Update existing task
                update_data = {}
                if task_result is not None:
                    update_data['task_result'] = task_result
                if task_status:
                    update_data['status'] = TaskStatus(task_status)
                if error_message is not None:
                    update_data['error_message'] = error_message
                if report_path is not None:
                    update_data['report_path'] = report_path
                if task_status == "running" and not existing_task.started_at:
                    update_data['started_at'] = func.now()
                if task_status in ["completed", "failed", "stopped"]:
                    update_data['completed_at'] = func.now()

                await db.execute(
                    update(Task).where(Task.task_id == task_id).values(**update_data)
                )
                await db.refresh(existing_task)
                return existing_task
            else:
                # DEBUG: Log the type and content of mcp_server_config before saving
                logger.info(
                    f"Creating task with mcp_server_config type: {type(mcp_server_config)}, value: {mcp_server_config}")

                # Serialize mcp_server_config to JSON string if it's a dict
                if isinstance(mcp_server_config, dict):
                    mcp_server_config_json = json.dumps(mcp_server_config)
                    logger.info(f"Converted dict to JSON string: {mcp_server_config_json}")
                else:
                    mcp_server_config_json = mcp_server_config

                # Create new task
                task = Task(
                    task_id=task_id,
                    session_id=session_id,
                    task_description=task_description,
                    status=TaskStatus(task_status),
                    llm_profile_name=llm_profile_name,
                    upload_files_path=upload_files_path,
                    workspace_dir=workspace_dir,
                    mcp_server_config=mcp_server_config_json,
                    task_result=task_result,
                    error_message=error_message,
                    report_path=report_path,
                    agent_mode=agent_mode
                )

                db.add(task)
                await db.flush()
                await db.refresh(task)
                return task

        except Exception as e:
            logger.error(f"Failed to save task {task_id}: {e}")
            raise

    @staticmethod
    async def get_task(db: AsyncSession, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        try:
            result = await db.execute(select(Task).where(Task.task_id == task_id))
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get task {task_id}: {e}")
            raise

    @staticmethod
    async def get_tasks_by_session(
            db: AsyncSession,
            session_id: str,
            limit: int = 50,
            offset: int = 0
    ) -> List[Task]:
        """Get all tasks for a session"""
        try:
            result = await db.execute(
                select(Task)
                .where(Task.session_id == session_id)
                .order_by(desc(Task.created_at))
                .limit(limit)
                .offset(offset)
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get tasks for session {session_id}: {e}")
            raise

    @staticmethod
    async def get_recent_tasks(db: AsyncSession, limit: int = -1) -> List[Task]:
        """Get recent tasks"""
        try:
            query = select(Task).order_by(desc(Task.created_at))

            # Handle -1 as "get all records"
            if limit != -1:
                query = query.limit(limit)

            result = await db.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get recent tasks: {e}")
            raise

    @staticmethod
    async def get_all_sessions(
            db: AsyncSession,
            limit: int = -1,
            offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get all unique sessions with task counts and metadata"""
        try:
            # Get distinct session_ids with aggregated data
            query = select(
                Task.session_id,
                func.count(Task.task_id).label('task_count'),
                func.min(Task.created_at).label('created_at'),
                func.max(Task.created_at).label('last_activity'),
                func.max(Task.status).label('latest_status')
            ).group_by(Task.session_id).order_by(desc(func.max(Task.created_at)))

            # Handle -1 as "get all records"
            if limit != -1:
                query = query.limit(limit)

            # Always apply offset if provided
            if offset > 0:
                query = query.offset(offset)

            result = await db.execute(query)

            sessions = []
            for row in result.all():
                sessions.append({
                    'session_id': row.session_id,
                    'task_count': row.task_count,
                    'created_at': row.created_at.isoformat() if row.created_at else None,
                    'last_activity': row.last_activity.isoformat() if row.last_activity else None,
                    'status': row.latest_status.value if row.latest_status else 'unknown'
                })

            return sessions
        except Exception as e:
            logger.error(f"Failed to get all sessions: {e}")
            raise

    @staticmethod
    async def update_task_status(
            db: AsyncSession,
            task_id: str,
            status: str,
            error_message: Optional[str] = None,
            task_result: Optional[str] = None,
            report_path: Optional[str] = None
    ) -> bool:
        """Update task status"""
        try:
            update_data = {
                'status': TaskStatus(status)
            }

            if status == "running":
                update_data['started_at'] = func.now()
            elif status in ["completed", "failed", "stopped"]:
                update_data['completed_at'] = func.now()

            if error_message:
                update_data['error_message'] = error_message
            if task_result:
                update_data['task_result'] = task_result
            if report_path:
                update_data['report_path'] = report_path

            result = await db.execute(
                update(Task).where(Task.task_id == task_id).values(**update_data)
            )

            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update task status {task_id}: {e}")
            raise

    @staticmethod
    async def delete_task(db: AsyncSession, task_id: str) -> bool:
        """Delete a task"""
        try:
            result = await db.execute(delete(Task).where(Task.task_id == task_id))
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to delete task {task_id}: {e}")
            raise

    @staticmethod
    async def get_running_tasks(db: AsyncSession) -> List[Task]:
        """Get all currently running tasks"""
        try:
            result = await db.execute(
                select(Task).where(Task.status.in_([TaskStatus.RUNNING, TaskStatus.PAUSED]))
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get running tasks: {e}")
            raise

    @staticmethod
    async def get_active_task(db: AsyncSession) -> Optional[Task]:
        """Get currently running task (for single-task model)"""
        try:
            result = await db.execute(
                select(Task).where(Task.status == TaskStatus.RUNNING)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get active task: {e}")
            raise

    @staticmethod
    async def get_tasks_by_llm_profile(
            db: AsyncSession,
            llm_profile_name: str,
            limit: int = 50,
            offset: int = 0
    ) -> List[Task]:
        """Get tasks that used a specific LLM profile"""
        try:
            result = await db.execute(
                select(Task)
                .where(Task.llm_profile_name == llm_profile_name)
                .order_by(desc(Task.created_at))
                .limit(limit)
                .offset(offset)
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get tasks for LLM profile {llm_profile_name}: {e}")
            raise

    @staticmethod
    async def update_task_completion(
            db: AsyncSession,
            task_id: str,
            task_result: Optional[str] = None,
            task_status: str = "completed",
            error_message: Optional[str] = None,
            report_path: Optional[str] = None
    ) -> bool:
        """Update task completion status and results"""
        try:
            update_data = {
                'status': TaskStatus(task_status),
                'completed_at': func.now()
            }

            if task_result is not None:
                update_data['task_result'] = task_result
            if error_message is not None:
                update_data['error_message'] = error_message
            if report_path is not None:
                update_data['report_path'] = report_path

            result = await db.execute(
                update(Task).where(Task.task_id == task_id).values(**update_data)
            )

            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update task completion {task_id}: {e}")
            raise

    @staticmethod
    async def get_task_counts_by_status(db: AsyncSession) -> Dict[str, int]:
        """Get count of tasks by status"""
        try:
            result = await db.execute(
                select(Task.status, func.count(Task.task_id))
                .group_by(Task.status)
            )

            counts = {}
            for status, count in result.all():
                counts[status.value] = count

            return counts
        except Exception as e:
            logger.error(f"Failed to get task counts by status: {e}")
            raise


class UploadedFileQueries:
    """Query operations for UploadedFile model"""

    @staticmethod
    async def create_file_record(
            db: AsyncSession,
            file_id: str,
            original_filename: str,
            stored_filename: str,
            file_path: str,
            session_id: Optional[str],
            file_size: int,
            mime_type: str,
            relative_path: str
    ) -> UploadedFile:
        """Create a new uploaded file record"""
        try:
            uploaded_file = UploadedFile(
                file_id=file_id,
                original_filename=original_filename,
                stored_filename=stored_filename,
                file_path=file_path,
                session_id=session_id,
                file_size=file_size,
                mime_type=mime_type,
                relative_path=relative_path
            )

            db.add(uploaded_file)
            await db.flush()
            await db.refresh(uploaded_file)
            return uploaded_file
        except Exception as e:
            logger.error(f"Failed to create file record {file_id}: {e}")
            raise

    @staticmethod
    async def get_file(db: AsyncSession, file_id: str) -> Optional[UploadedFile]:
        """Get uploaded file by ID"""
        try:
            result = await db.execute(
                select(UploadedFile).where(
                    and_(UploadedFile.file_id == file_id, UploadedFile.is_deleted == False)
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get file {file_id}: {e}")
            raise

    @staticmethod
    async def list_files(
            db: AsyncSession,
            session_id: Optional[str] = None,
            limit: int = -1,
            offset: int = 0,
            active_only: bool = True
    ) -> List[UploadedFile]:
        """List uploaded files with optional filtering"""
        try:
            query = select(UploadedFile)

            if active_only:
                query = query.where(UploadedFile.is_deleted == False)

            if session_id is not None:
                query = query.where(UploadedFile.session_id == session_id)

            query = query.order_by(desc(UploadedFile.upload_time))

            # Handle -1 as "get all records"
            if limit != -1:
                query = query.limit(limit)

            # Always apply offset if provided
            if offset > 0:
                query = query.offset(offset)

            result = await db.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            raise

    @staticmethod
    async def count_files(
            db: AsyncSession,
            session_id: Optional[str] = None,
            active_only: bool = True
    ) -> int:
        """Count uploaded files with optional filtering"""
        try:
            query = select(func.count(UploadedFile.file_id))

            if active_only:
                query = query.where(UploadedFile.is_deleted == False)

            if session_id is not None:
                query = query.where(UploadedFile.session_id == session_id)

            result = await db.execute(query)
            return result.scalar() or 0
        except Exception as e:
            logger.error(f"Failed to count files: {e}")
            raise

    @staticmethod
    async def delete_file(db: AsyncSession, file_id: str) -> bool:
        """Soft delete uploaded file by marking as deleted"""
        try:
            result = await db.execute(
                update(UploadedFile)
                .where(UploadedFile.file_id == file_id)
                .values(is_deleted=True, deleted_at=func.now())
            )
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {e}")
            raise

    @staticmethod
    async def hard_delete_file(db: AsyncSession, file_id: str) -> bool:
        """Permanently delete uploaded file record"""
        try:
            result = await db.execute(
                delete(UploadedFile).where(UploadedFile.file_id == file_id)
            )
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to hard delete file {file_id}: {e}")
            raise

    @staticmethod
    async def get_files_by_session(
            db: AsyncSession,
            session_id: str,
            limit: int = -1,
            offset: int = 0
    ) -> List[UploadedFile]:
        """Get all uploaded files for a specific session"""
        try:
            query = select(UploadedFile).where(and_(
                UploadedFile.session_id == session_id,
                UploadedFile.is_deleted == False
            )).order_by(desc(UploadedFile.upload_time))

            # Handle -1 as "get all records"
            if limit != -1:
                query = query.limit(limit)

            # Always apply offset if provided
            if offset > 0:
                query = query.offset(offset)

            result = await db.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get files for session {session_id}: {e}")
            raise

    @staticmethod
    async def cleanup_deleted_files(db: AsyncSession, days_old: int = 30) -> int:
        """Clean up files marked as deleted for more than specified days"""
        try:
            cutoff_date = func.now() - func.make_interval(days=days_old)

            result = await db.execute(
                delete(UploadedFile)
                .where(and_(
                    UploadedFile.is_deleted == True,
                    UploadedFile.deleted_at < cutoff_date
                ))
            )
            return result.rowcount
        except Exception as e:
            logger.error(f"Failed to cleanup deleted files: {e}")
            raise


class VoiceProfileQueries:
    """Query operations for VoiceProfile model"""

    @staticmethod
    async def create_profile(
            db: AsyncSession,
            voice_profile_name: str,
            voice_model_type: str,
            voice_model_name: str,
            api_key: Optional[str] = None,
            voice_meta_params: Optional[Dict[str, Any]] = None,
            description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new Voice profile with encrypted API key"""
        try:
            # Encrypt API key if provided
            encrypted_api_key = encrypt_api_key(api_key) if api_key else None

            profile = VoiceProfile(
                voice_profile_name=voice_profile_name,
                voice_model_type=VoiceModelType(voice_model_type),
                voice_model_name=voice_model_name,
                encrypted_api_key=encrypted_api_key,
                voice_meta_params=voice_meta_params or {},
                description=description
            )

            db.add(profile)
            await db.flush()
            await db.refresh(profile)

            # Extract data immediately to avoid greenlet issues
            profile_data = {
                "profile_id": profile.profile_id,
                "voice_profile_name": profile.voice_profile_name,
                "voice_model_type": profile.voice_model_type.value,
                "voice_model_name": profile.voice_model_name,
                "voice_meta_params": profile.voice_meta_params,
                "description": profile.description,
                "is_active": profile.is_active,
                "created_at": profile.created_at,
                "updated_at": profile.updated_at,
                "last_used_at": profile.last_used_at
            }

            return profile_data
        except Exception as e:
            logger.error(f"Failed to create Voice profile {voice_profile_name}: {e}")
            raise

    @staticmethod
    async def get_profile(db: AsyncSession, voice_profile_name: str) -> Optional[VoiceProfile]:
        """Get Voice profile by name"""
        try:
            result = await db.execute(
                select(VoiceProfile).where(VoiceProfile.voice_profile_name == voice_profile_name)
            )
            profile = result.scalar_one_or_none()
            if profile:
                # Ensure all attributes are loaded by accessing them
                _ = (profile.profile_id, profile.created_at, profile.updated_at,
                     profile.last_used_at, profile.is_active)
            return profile
        except Exception as e:
            logger.error(f"Failed to get Voice profile {voice_profile_name}: {e}")
            raise

    @staticmethod
    async def get_profile_with_decrypted_key(db: AsyncSession, voice_profile_name: str) -> Optional[Dict[str, Any]]:
        """Get Voice profile with decrypted API key"""
        try:
            profile = await VoiceProfileQueries.get_profile(db, voice_profile_name)
            if not profile:
                return None

            # Decrypt API key
            decrypted_api_key = decrypt_api_key(profile.encrypted_api_key) if profile.encrypted_api_key else None

            return {
                "profile_id": profile.profile_id,
                "voice_profile_name": profile.voice_profile_name,
                "voice_model_type": profile.voice_model_type.value,
                "voice_model_name": profile.voice_model_name,
                "api_key": decrypted_api_key,  # Decrypted for use
                "voice_meta_params": profile.voice_meta_params,
                "description": profile.description,
                "is_active": profile.is_active,
                "created_at": profile.created_at,
                "updated_at": profile.updated_at,
                "last_used_at": profile.last_used_at
            }
        except Exception as e:
            logger.error(f"Failed to get Voice profile with decrypted key {voice_profile_name}: {e}")
            raise

    @staticmethod
    async def list_profiles(
            db: AsyncSession,
            voice_model_type: Optional[str] = None,
            active_only: bool = True,
            limit: int = 50,
            offset: int = 0
    ) -> List[VoiceProfile]:
        """List Voice profiles"""
        try:
            query = select(VoiceProfile)

            if active_only:
                query = query.where(VoiceProfile.is_active == True)
            
            if voice_model_type:
                query = query.where(VoiceProfile.voice_model_type == VoiceModelType(voice_model_type))

            query = query.order_by(desc(VoiceProfile.last_used_at), desc(VoiceProfile.created_at))
            query = query.limit(limit).offset(offset)

            result = await db.execute(query)
            profiles = result.scalars().all()

            # Ensure all attributes are loaded for each profile
            for profile in profiles:
                _ = (profile.profile_id, profile.created_at, profile.updated_at,
                     profile.last_used_at, profile.is_active)

            return profiles
        except Exception as e:
            logger.error(f"Failed to list Voice profiles: {e}")
            raise

    @staticmethod
    async def update_profile(
            db: AsyncSession,
            voice_profile_name: str,
            updates: Dict[str, Any]
    ) -> bool:
        """Update Voice profile"""
        try:
            # Handle API key encryption if present
            if "api_key" in updates:
                api_key = updates.pop("api_key")
                if api_key:
                    updates["encrypted_api_key"] = encrypt_api_key(api_key)
                else:
                    updates["encrypted_api_key"] = None

            # Handle voice_model_type enum conversion
            if "voice_model_type" in updates:
                updates["voice_model_type"] = VoiceModelType(updates["voice_model_type"])

            result = await db.execute(
                update(VoiceProfile)
                .where(VoiceProfile.voice_profile_name == voice_profile_name)
                .values(**updates)
            )

            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update Voice profile {voice_profile_name}: {e}")
            raise

    @staticmethod
    async def delete_profile(db: AsyncSession, voice_profile_name: str) -> bool:
        """Delete Voice profile"""
        try:
            result = await db.execute(
                delete(VoiceProfile).where(VoiceProfile.voice_profile_name == voice_profile_name)
            )
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to delete Voice profile {voice_profile_name}: {e}")
            raise


    @staticmethod
    async def update_last_used(db: AsyncSession, voice_profile_name: str) -> bool:
        """Update the last_used_at timestamp for a profile"""
        try:
            result = await db.execute(
                update(VoiceProfile)
                .where(VoiceProfile.voice_profile_name == voice_profile_name)
                .values(last_used_at=func.now())
            )
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update last_used for Voice profile {voice_profile_name}: {e}")
            raise
