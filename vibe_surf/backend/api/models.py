"""
API Request/Response Models for VibeSurf Backend

Pydantic models for API serialization and validation.
With LLM Profile management support.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

# LLM Profile Models
class LLMProfileCreateRequest(BaseModel):
    """Request model for creating a new LLM profile"""
    profile_name: str = Field(description="Unique profile name", min_length=1, max_length=100)
    provider: str = Field(description="LLM provider (openai, anthropic, google, azure_openai)")
    model: str = Field(description="Model name")
    api_key: Optional[str] = Field(default=None, description="API key (will be encrypted)")
    base_url: Optional[str] = Field(default=None, description="Custom base URL")
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    frequency_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0)
    seed: Optional[int] = Field(default=None)
    provider_config: Optional[Dict[str, Any]] = Field(default=None, description="Provider-specific config")
    description: Optional[str] = Field(default=None, description="Profile description")
    is_default: bool = Field(default=False, description="Set as default profile")

class LLMProfileUpdateRequest(BaseModel):
    """Request model for updating an LLM profile"""
    provider: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    frequency_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0)
    seed: Optional[int] = None
    provider_config: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None

class LLMProfileResponse(BaseModel):
    """Response model for LLM profile data (without API key)"""
    profile_id: str
    profile_name: str
    provider: str
    model: str
    base_url: Optional[str] = None
    # Note: API key is intentionally excluded from response
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    seed: Optional[int] = None
    provider_config: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    is_active: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# MCP Profile Models
class McpProfileCreateRequest(BaseModel):
    """Request model for creating a new MCP profile"""
    display_name: str = Field(description="Display name for MCP profile", min_length=1, max_length=100)
    mcp_server_name: str = Field(description="MCP server name/identifier", min_length=1, max_length=100)
    mcp_server_params: Dict[str, Any] = Field(description="MCP server parameters (command, args, etc.)")
    description: Optional[str] = Field(default=None, description="Profile description")

class McpProfileUpdateRequest(BaseModel):
    """Request model for updating an MCP profile"""
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    mcp_server_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    mcp_server_params: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class McpProfileResponse(BaseModel):
    """Response model for MCP profile data"""
    mcp_id: str
    display_name: str
    mcp_server_name: str
    mcp_server_params: Dict[str, Any]
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Task Models
class TaskCreateRequest(BaseModel):
    """Request model for creating a new task"""
    session_id: str = Field(description="Session identifier")
    task_description: str = Field(description="The task description")
    llm_profile_name: str = Field(description="LLM profile name to use")
    upload_files_path: Optional[str] = Field(default=None, description="Path to uploaded files")
    mcp_server_config: Optional[Dict[str, Any]] = Field(default=None, description="MCP server configuration")
    agent_mode: str = Field(default="thinking", description="Agent mode: 'thinking', 'no-thinking', or 'flash'")

class TaskControlRequest(BaseModel):
    """Request model for task control operations (pause/resume/stop)"""
    reason: Optional[str] = Field(default=None, description="Reason for the operation")

class TaskResponse(BaseModel):
    """Response model for task data"""
    task_id: str
    session_id: str
    task_description: str
    status: str
    llm_profile_name: str
    upload_files_path: Optional[str] = None
    workspace_dir: Optional[str] = None
    mcp_server_config: Optional[Dict[str, Any]] = None
    agent_mode: str = "thinking"
    task_result: Optional[str] = None
    error_message: Optional[str] = None
    report_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    task_metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True
    
    @classmethod
    def from_orm(cls, task):
        """Create response from SQLAlchemy Task model"""
        return cls(
            task_id=task.task_id,
            session_id=task.session_id,
            task_description=task.task_description,
            status=task.status.value,
            llm_profile_name=task.llm_profile_name,
            upload_files_path=task.upload_files_path,
            workspace_dir=task.workspace_dir,
            mcp_server_config=task.mcp_server_config,
            agent_mode=task.agent_mode,
            task_result=task.task_result,
            error_message=task.error_message,
            report_path=task.report_path,
            created_at=task.created_at,
            updated_at=task.updated_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            task_metadata=task.task_metadata
        )

class TaskStatusResponse(BaseModel):
    """Response model for task status information"""
    task_id: Optional[str] = None
    session_id: Optional[str] = None
    status: Optional[str] = None
    task_description: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    error_message: Optional[str] = None
    is_running: bool = False

class TaskListResponse(BaseModel):
    """Response model for task list"""
    tasks: List[TaskResponse]
    total_count: int
    session_id: Optional[str] = None

class ErrorResponse(BaseModel):
    """Standard error response model"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class ControlOperationResponse(BaseModel):
    """Response model for control operations"""
    success: bool
    message: str
    operation: str
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None

# Activity Log Models (for VibeSurf agent activity)
class ActivityLogEntry(BaseModel):
    """Model for VibeSurf agent activity log entry"""
    timestamp: datetime
    level: str
    message: str
    metadata: Optional[Dict[str, Any]] = None

class ActivityLogResponse(BaseModel):
    """Response model for activity logs"""
    logs: List[ActivityLogEntry]
    total_count: int
    session_id: Optional[str] = None
    task_id: Optional[str] = None

# Activity API Request Models
class ActivityQueryRequest(BaseModel):
    """Request model for getting recent tasks"""
    limit: int = Field(default=-1, ge=-1, le=1000, description="Number of recent tasks to retrieve (-1 for all)")

class SessionActivityQueryRequest(BaseModel):
    """Request model for getting session activity logs"""
    limit: int = Field(default=-1, ge=-1, le=1000, description="Number of activity logs to retrieve (-1 for all)")
    message_index: Optional[int] = Field(default=None, ge=0, description="Specific message index to retrieve")

# File API Request Models
class FileUploadRequest(BaseModel):
    """Request model for file upload (for form validation)"""
    session_id: Optional[str] = Field(default=None, description="Session ID for file association")

class FileListQueryRequest(BaseModel):
    """Request model for listing uploaded files"""
    session_id: Optional[str] = Field(default=None, description="Filter by session ID")
    limit: int = Field(default=-1, ge=-1, le=1000, description="Number of files to retrieve (-1 for all)")
    offset: int = Field(default=0, ge=0, description="Number of files to skip")

class SessionFilesQueryRequest(BaseModel):
    """Request model for listing session files"""
    include_directories: bool = Field(default=False, description="Whether to include directories in the response")

# File Upload Models
class UploadedFileResponse(BaseModel):
    """Response model for uploaded file information"""
    filename: str
    file_path: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    uploaded_at: datetime

# Configuration Models (for config endpoints)
class LLMConfigResponse(BaseModel):
    """Response model for LLM configuration"""
    provider: str
    model: str
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    available_providers: List[str] = []

class ControllerConfigRequest(BaseModel):
    """Request model for updating tools configuration"""
    exclude_actions: Optional[List[str]] = Field(default=None, description="Actions to exclude from execution")
    max_actions_per_task: Optional[int] = Field(default=None, gt=0, description="Maximum actions per task")
    display_files_in_done_text: Optional[bool] = Field(default=None, description="Whether to display files in done text")

class ControllerConfigResponse(BaseModel):
    """Response model for tools configuration"""
    exclude_actions: List[str] = []
    max_actions_per_task: int = 100
    display_files_in_done_text: bool = True