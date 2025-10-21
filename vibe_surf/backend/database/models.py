"""
Database Models for VibeSurf Backend - With LLM Profile Management

SQLAlchemy models for task execution system with LLM profile management.
"""

from sqlalchemy import Column, String, Text, DateTime, Enum, JSON, Boolean, Index, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
import enum
from uuid import uuid4

Base = declarative_base()

# Enums for type safety
class TaskStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"

class VoiceModelType(enum.Enum):
    ASR = "asr"
    TTS = "tts"

class VoiceProfile(Base):
    """Voice Profile model for managing voice model configurations with encrypted API keys"""
    __tablename__ = 'voice_profiles'
    
    # Primary identifier
    profile_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    voice_profile_name = Column(String(100), nullable=False, unique=True)  # User-defined unique name
    
    # Voice Model Configuration
    voice_model_type = Column(Enum(VoiceModelType, values_callable=lambda obj: [e.value for e in obj]), nullable=False)  # asr or tts
    voice_model_name = Column(String(100), nullable=False)
    encrypted_api_key = Column(Text, nullable=True)  # Encrypted API key using MAC address
    
    # Voice model parameters (stored as JSON to allow flexibility)
    voice_meta_params = Column(JSON, nullable=True)  # Model-specific parameters
    
    # Profile metadata
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    last_used_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<VoiceProfile(voice_profile_name={self.voice_profile_name}, voice_model_name={self.voice_model_name}, type={self.voice_model_type.value})>"

class LLMProfile(Base):
    """LLM Profile model for managing LLM configurations with encrypted API keys"""
    __tablename__ = 'llm_profiles'
    
    # Primary identifier
    profile_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    profile_name = Column(String(100), nullable=False, unique=True)  # User-defined unique name
    
    # LLM Configuration
    provider = Column(String(50), nullable=False)  # openai, anthropic, google, azure_openai, etc.
    model = Column(String(100), nullable=False)
    base_url = Column(String(500), nullable=True)
    encrypted_api_key = Column(Text, nullable=True)  # Encrypted API key using MAC address
    
    # LLM Parameters (stored as JSON to allow null values)
    temperature = Column(JSON, nullable=True)  # Allow float or null
    max_tokens = Column(JSON, nullable=True)   # Allow int or null
    top_p = Column(JSON, nullable=True)
    frequency_penalty = Column(JSON, nullable=True)
    seed = Column(JSON, nullable=True)
    
    # Provider-specific configuration
    provider_config = Column(JSON, nullable=True)
    
    # Profile metadata
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    last_used_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<LLMProfile(profile_name={self.profile_name}, provider={self.provider}, model={self.model})>"

class Task(Base):
    """Task model with LLM profile reference and workspace directory"""
    __tablename__ = 'tasks'
    
    # Primary identifier
    task_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    
    # Session tracking
    session_id = Column(String(36), nullable=False)
    
    # Task definition
    task_description = Column(Text, nullable=False)
    status = Column(Enum(TaskStatus, values_callable=lambda obj: [e.value for e in obj]), nullable=False, default=TaskStatus.PENDING)
    
    # LLM Profile reference (instead of storing LLM config directly)
    llm_profile_name = Column(String(100), nullable=False)  # Reference to LLMProfile.profile_name
    
    # File uploads and workspace
    upload_files_path = Column(String(500), nullable=True)  # Path to uploaded files
    workspace_dir = Column(String(500), nullable=True)     # Workspace directory for this task
    
    # Configuration (JSON strings without API keys)
    mcp_server_config = Column(Text, nullable=True)  # MCP server config as JSON string
    
    # Agent execution mode
    agent_mode = Column(String(50), nullable=False, default='thinking')  # Agent mode: 'thinking' or 'direct'
    
    # Results
    task_result = Column(Text, nullable=True)  # Final markdown result
    error_message = Column(Text, nullable=True)
    report_path = Column(String(500), nullable=True)  # Generated report file path
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Additional metadata
    task_metadata = Column(JSON, nullable=True)  # Additional context
    
    def __repr__(self):
        return f"<Task(task_id={self.task_id}, status={self.status.value}, llm_profile={self.llm_profile_name})>"

class UploadedFile(Base):
    """Model for tracking uploaded files"""
    __tablename__ = "uploaded_files"
    
    file_id = Column(String(36), primary_key=True)  # UUID7 string
    original_filename = Column(String(255), nullable=False, index=True)
    stored_filename = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)
    session_id = Column(String(255), nullable=True, index=True)
    file_size = Column(BigInteger, nullable=False)
    mime_type = Column(String(100), nullable=False)
    upload_time = Column(DateTime, default=func.now(), nullable=False, index=True)
    relative_path = Column(Text, nullable=False)  # Relative to workspace_dir
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<UploadedFile(file_id={self.file_id}, filename={self.original_filename}, session={self.session_id})>"

# Create useful indexes for performance
Index('idx_llm_profiles_name', LLMProfile.profile_name)
Index('idx_llm_profiles_active', LLMProfile.is_active)
Index('idx_llm_profiles_default', LLMProfile.is_default)
Index('idx_llm_profiles_provider', LLMProfile.provider)

Index('idx_tasks_status', Task.status)
Index('idx_tasks_session', Task.session_id)
Index('idx_tasks_llm_profile', Task.llm_profile_name)
Index('idx_tasks_created', Task.created_at)

class McpProfile(Base):
    """MCP Profile model for managing MCP server configurations"""
    __tablename__ = 'mcp_profiles'
    
    # Primary identifier
    mcp_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    display_name = Column(String(100), nullable=False, unique=True)  # User-friendly name
    mcp_server_name = Column(String(100), nullable=False, unique=True)  # Server identifier (e.g., "filesystem", "markitdown")
    
    # MCP Server Configuration
    mcp_server_params = Column(JSON, nullable=False)  # {"command": "npx", "args": [...]}
    
    # Profile metadata
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    last_used_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<McpProfile(display_name={self.display_name}, server_name={self.mcp_server_name}, active={self.is_active})>"

class ComposioToolkit(Base):
    """Composio Toolkit model for managing Composio app integrations"""
    __tablename__ = 'composio_toolkits'
    
    # Primary identifier
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(100), nullable=False)
    slug = Column(String(100), nullable=False, unique=True)
    
    # Toolkit information
    description = Column(Text, nullable=True)
    logo = Column(Text, nullable=True)  # URL to logo
    app_url = Column(Text, nullable=True)
    
    # Configuration
    enabled = Column(Boolean, default=False, nullable=False)
    tools = Column(Text, nullable=True)  # JSON string storing tool_name: 0|1 mapping
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<ComposioToolkit(name={self.name}, slug={self.slug}, enabled={self.enabled})>"

class Credential(Base):
    """Credential model for storing encrypted API keys and other sensitive data"""
    __tablename__ = 'credentials'
    
    # Primary identifier
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    key_name = Column(String(100), nullable=False, unique=True)  # e.g., "COMPOSIO_API_KEY"
    encrypted_value = Column(Text, nullable=True)  # Encrypted value using MAC address
    
    # Metadata
    description = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Credential(key_name={self.key_name})>"

Index('idx_uploaded_files_session_time', UploadedFile.session_id, UploadedFile.upload_time)
Index('idx_uploaded_files_active', UploadedFile.is_deleted, UploadedFile.upload_time)
Index('idx_uploaded_files_filename', UploadedFile.original_filename)

# MCP Profile indexes
Index('idx_mcp_profiles_display_name', McpProfile.display_name)
Index('idx_mcp_profiles_server_name', McpProfile.mcp_server_name)
Index('idx_mcp_profiles_active', McpProfile.is_active)

# Voice Profile indexes
Index('idx_voice_profiles_name', VoiceProfile.voice_profile_name)
Index('idx_voice_profiles_type', VoiceProfile.voice_model_type)
Index('idx_voice_profiles_active', VoiceProfile.is_active)

# Composio Toolkit indexes
Index('idx_composio_toolkits_name', ComposioToolkit.name)
Index('idx_composio_toolkits_slug', ComposioToolkit.slug)
Index('idx_composio_toolkits_enabled', ComposioToolkit.enabled)

# Credential indexes
Index('idx_credentials_key_name', Credential.key_name)

class Schedule(Base):
    """Schedule model for managing workflow schedules with cron expressions"""
    __tablename__ = 'schedules'
    
    # Primary identifier
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    flow_id = Column(String(36), nullable=False, unique=True)  # One schedule per flow
    
    # Schedule Configuration
    cron_expression = Column(String(100), nullable=True)  # Standard cron format, nullable for disabled schedules
    
    # Schedule metadata
    is_enabled = Column(Boolean, default=True, nullable=False)
    description = Column(Text, nullable=True)
    
    # Execution tracking
    last_execution_at = Column(DateTime, nullable=True)
    next_execution_at = Column(DateTime, nullable=True)
    execution_count = Column(BigInteger, default=0, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Schedule(flow_id={self.flow_id}, cron={self.cron_expression}, enabled={self.is_enabled})>"

# Schedule indexes
Index('idx_schedules_flow_id', Schedule.flow_id)
Index('idx_schedules_enabled', Schedule.is_enabled)
Index('idx_schedules_next_execution', Schedule.next_execution_at)
Index('idx_schedules_cron', Schedule.cron_expression)