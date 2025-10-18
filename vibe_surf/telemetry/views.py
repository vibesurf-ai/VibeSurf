from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

from browser_use.config import is_running_in_docker


@dataclass
class BaseTelemetryEvent(ABC):
	@property
	@abstractmethod
	def name(self) -> str:
		pass

	@property
	def properties(self) -> dict[str, Any]:
		props = {k: v for k, v in asdict(self).items() if k != 'name'}
		# Add Docker context if running in Docker
		props['is_docker'] = is_running_in_docker()
		return props


@dataclass
class AgentTelemetryEvent(BaseTelemetryEvent):
	# start details
	task: str
	model: str
	model_provider: str
	max_steps: int
	max_actions_per_step: int
	use_vision: bool
	version: str
	source: str
	cdp_url: str | None
	# step details
	action_errors: Sequence[str | None]
	action_history: Sequence[list[dict] | None]
	urls_visited: Sequence[str | None]
	# end details
	steps: int
	total_input_tokens: int
	total_duration_seconds: float
	success: bool | None
	final_result_response: str | None
	error_message: str | None

	name: str = 'agent_event'


@dataclass
class MCPClientTelemetryEvent(BaseTelemetryEvent):
	"""Telemetry event for MCP client usage"""

	server_name: str
	command: str
	tools_discovered: int
	version: str
	action: str  # 'connect', 'disconnect', 'tool_call'
	tool_name: str | None = None
	duration_seconds: float | None = None
	error_message: str | None = None

	name: str = 'mcp_client_event'


@dataclass
class MCPServerTelemetryEvent(BaseTelemetryEvent):
	"""Telemetry event for MCP server usage"""

	version: str
	action: str  # 'start', 'stop', 'tool_call'
	tool_name: str | None = None
	duration_seconds: float | None = None
	error_message: str | None = None
	parent_process_cmdline: str | None = None

	name: str = 'mcp_server_event'


@dataclass
class ComposioTelemetryEvent(BaseTelemetryEvent):
	"""Telemetry event for Composio client usage"""

	toolkit_slugs: list[str]
	tools_registered: int
	version: str
	action: str  # 'register', 'unregister', 'tool_call'
	toolkit_slug: str | None = None
	tool_name: str | None = None
	duration_seconds: float | None = None
	error_message: str | None = None

	name: str = 'composio_client_event'


@dataclass
class CLITelemetryEvent(BaseTelemetryEvent):
	"""Telemetry event for CLI usage"""

	version: str
	action: str  # 'start', 'message_sent', 'task_completed', 'error'
	mode: str  # 'interactive', 'oneshot', 'mcp_server'
	model: str | None = None
	model_provider: str | None = None
	browser_path: str | None = None
	duration_seconds: float | None = None
	error_message: str | None = None

	name: str = 'cli_event'


@dataclass
class VibeSurfAgentTelemetryEvent(BaseTelemetryEvent):
	"""Telemetry event for VibeSurf Agent usage"""
	
	version: str
	action: str  # 'start', 'task_completed', 'error'
	task_description: str | None = None
	model: str | None = None
	model_provider: str | None = None
	duration_seconds: float | None = None
	success: bool | None = None
	error_message: str | None = None
	session_id: str | None = None
	
	name: str = 'vibesurf_agent_event'


@dataclass
class ReportWriterTelemetryEvent(BaseTelemetryEvent):
	"""Telemetry event for Report Writer Agent usage"""
	
	version: str
	action: str  # 'start', 'report_completed', 'error'
	model: str | None = None
	model_provider: str | None = None
	duration_seconds: float | None = None
	success: bool | None = None
	error_message: str | None = None
	report_type: str | None = None
	
	name: str = 'report_writer_event'


@dataclass
class BackendTelemetryEvent(BaseTelemetryEvent):
	"""Telemetry event for Backend API usage"""
	
	version: str
	action: str  # 'startup', 'shutdown', 'api_call'
	api_endpoint: str | None = None
	duration_seconds: float | None = None
	error_message: str | None = None
	
	name: str = 'backend_event'


@dataclass
class VibeSurfAgentParsedOutputEvent(BaseTelemetryEvent):
	"""Telemetry event for VibeSurf Agent parsed output"""
	
	version: str
	parsed_output: str | None = None
	action_count: int | None = None
	action_types: list[str] | None = None
	model: str | None = None
	model_provider: str | None = None
	session_id: str | None = None
	thinking: str | None = None
	
	name: str = 'vibesurf_agent_parsed_output'


@dataclass
class VibeSurfAgentExceptionEvent(BaseTelemetryEvent):
	"""Telemetry event for VibeSurf Agent exceptions"""
	
	version: str
	error_message: str
	error_type: str | None = None
	traceback: str | None = None
	model: str | None = None
	model_provider: str | None = None
	session_id: str | None = None
	function_name: str | None = None
	
	name: str = 'vibesurf_agent_exception'
