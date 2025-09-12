"""
JSON Schema Definitions for VibeSurf Database - Simplified Single Task Model

Pydantic models for validating JSON fields in the simplified Task table.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class TaskMetadata(BaseModel):
    """Schema for Task.task_metadata JSON field"""
    
    # Execution summary
    execution_duration_seconds: Optional[float] = None
    total_actions: Optional[int] = None
    
    # Results summary
    generated_report_path: Optional[str] = None
    final_summary: Optional[str] = None
    
    # Control state history
    control_history: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Error context
    last_error: Optional[str] = None
    error_recovery_attempts: int = 0
    
    # User context
    created_via: str = "api"

class LLMConfiguration(BaseModel):
    """Schema for Task.llm_config JSON field"""
    
    model: str
    base_url: Optional[str] = None
    # Note: API key is intentionally excluded from stored config
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    seed: Optional[int] = None
    
    # Provider-specific settings
    provider: str = "openai"  # 'openai', 'azure', 'anthropic', etc.
    provider_config: Dict[str, Any] = Field(default_factory=dict)

class McpServerParams(BaseModel):
    """Schema for MCP server parameters configuration"""
    command: str  # e.g., "npx", "docker"
    args: List[str]  # command arguments
    env: Optional[Dict[str, str]] = None  # environment variables
    cwd: Optional[str] = None  # working directory
    timeout: Optional[int] = None  # timeout in seconds

class McpServerConfig(BaseModel):
    """Schema for MCP server configuration in Task.mcp_server_config"""
    mcpServers: Dict[str, McpServerParams] = Field(default_factory=dict)

class ControllerConfiguration(BaseModel):
    """Schema for Task.mcp_server_config JSON field (legacy tools config)"""
    
    # Action control
    exclude_actions: List[str] = Field(default_factory=list)
    max_actions_per_task: Optional[int] = 100
    
    # Output configuration
    display_files_in_done_text: bool = True
    save_screenshots: bool = True
    
    # Error handling
    continue_on_action_error: bool = False
    max_retries_per_action: int = 3

# Schema validation utilities
JSON_SCHEMAS = {
    'task_metadata': TaskMetadata,
    'llm_configuration': LLMConfiguration,
    'controller_configuration': ControllerConfiguration,
    'mcp_server_config': McpServerConfig,
    'mcp_server_params': McpServerParams,
}

def validate_json_field(schema_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize JSON field data using appropriate schema"""
    if schema_name not in JSON_SCHEMAS:
        return data
    
    schema_class = JSON_SCHEMAS[schema_name]
    validated = schema_class(**data)
    return validated.model_dump(exclude_none=True)

def get_schema_for_config_type(config_type: str) -> Optional[BaseModel]:
    """Get appropriate schema based on configuration type"""
    schema_mapping = {
        'llm_config': LLMConfiguration,
        'controller_config': ControllerConfiguration,  # Legacy support
        'mcp_server_config': McpServerConfig,
    }
    return schema_mapping.get(config_type)