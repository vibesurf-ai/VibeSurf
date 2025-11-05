"""Composio client integration for VibeSurf tools.

This module provides integration between Composio toolkits and VibeSurf's action registry.
Composio tools are dynamically discovered and registered as VibeSurf actions.

Example usage:
    from vibe_surf.tools.composio_client import ComposioClient
    from vibe_surf.tools.vibesurf_tools import VibeSurfTools

    tools = VibeSurfTools()

    # Connect to Composio
    composio_client = ComposioClient(
        composio_instance=composio_instance
    )

    # Register all Composio tools as VibeSurf actions
    await composio_client.register_to_tools(tools, toolkit_tools_dict)
"""

import asyncio
import logging
import pdb
import time
import json
from typing import Any, Dict, Optional, List

from pydantic import BaseModel, ConfigDict, Field, create_model

from browser_use.agent.views import ActionResult
from vibe_surf.logger import get_logger
from vibe_surf.telemetry.service import ProductTelemetry
from vibe_surf.telemetry.views import ComposioTelemetryEvent
from vibe_surf.utils import get_vibesurf_version

logger = get_logger(__name__)


class ComposioClient:
    """Client for connecting to Composio and exposing toolkit tools as VibeSurf actions."""

    def __init__(
        self,
        composio_instance: Optional[Any] = None,
    ):
        """Initialize Composio client.

        Args:
            composio_instance: Composio instance (optional, can be set later)
        """
        self.composio_instance = composio_instance
        self._registered_actions: set[str] = set()
        self._toolkit_tools: Dict[str, List[Dict]] = {}
        self._telemetry = ProductTelemetry()

    def update_composio_instance(self, composio_instance: Any):
        """Update the Composio instance"""
        self.composio_instance = composio_instance

    async def register_to_tools(
        self,
        tools,  # VibeSurfTools instance
        toolkit_tools_dict: Dict[str, List[Dict]],
        prefix: str = "cpo.",
    ) -> None:
        """Register Composio tools as actions in the VibeSurf tools.

        Args:
            tools: VibeSurf tools instance to register actions to
            toolkit_tools_dict: Dict of toolkit_slug -> tools list
            prefix: Prefix to add to action names (e.g., "cpo.")
        """
        if not self.composio_instance:
            logger.warning("Composio instance not available, skipping registration")
            return

        self._toolkit_tools = toolkit_tools_dict
        registry = tools.registry

        for toolkit_slug, tools_list in toolkit_tools_dict.items():
            # Parse tools if it's a JSON string
            if isinstance(tools_list, str):
                try:
                    tools_list = json.loads(tools_list)
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Failed to parse tools for toolkit {toolkit_slug}: {e}")
                    continue

            if not isinstance(tools_list, list):
                logger.warning(f"Tools for toolkit {toolkit_slug} is not a list: {type(tools_list)}")
                continue

            for tool_info in tools_list:
                if not isinstance(tool_info, dict):
                    continue

                tool_name = tool_info.get('name')
                if not tool_name:
                    continue

                # Skip if tool is disabled
                if not tool_info.get('enabled', True):
                    continue

                # Apply prefix
                action_name = f'{prefix}{toolkit_slug}.{tool_name}'

                # Skip if already registered
                if action_name in self._registered_actions:
                    continue

                # Register the tool as an action
                self._register_tool_as_action(registry, action_name, toolkit_slug, tool_info)
                self._registered_actions.add(action_name)

        logger.info(f"✅ Registered {len(self._registered_actions)} Composio tools as VibeSurf actions")
        
        # Capture telemetry for registration
        self._telemetry.capture(
            ComposioTelemetryEvent(
                toolkit_slugs=list(toolkit_tools_dict.keys()),
                tools_registered=len(self._registered_actions),
                version=get_vibesurf_version(),
                action='register'
            )
        )

    def _register_tool_as_action(self, registry, action_name: str, toolkit_slug: str, tool_info: Dict) -> None:
        """Register a single Composio tool as a VibeSurf action.

        Args:
            registry: VibeSurf registry to register action to
            action_name: Name for the registered action
            toolkit_slug: Toolkit slug 
            tool_info: Tool information dictionary
        """
        # Parse tool parameters to create Pydantic model
        param_fields = {}
        tool_name = tool_info.get('name', '')
        description = tool_info.get('description', f'Composio tool: {tool_name}')
        parameters = tool_info.get('parameters', {})

        if parameters and isinstance(parameters, dict):
            # Handle JSON Schema parameters
            properties = parameters.get('properties', {})
            required = set(parameters.get('required', []))

            for param_name, param_schema in properties.items():
                # Convert JSON Schema type to Python type
                param_type = self._json_schema_to_python_type(param_schema, f'{param_name}')

                # Determine if field is required and handle defaults
                if param_name in required:
                    default = ...  # Required field
                else:
                    # Optional field - make type optional and handle default
                    param_type = param_type | None
                    if 'default' in param_schema:
                        default = param_schema['default']
                    else:
                        default = None

                # Add field with description if available
                field_kwargs = {}
                if 'description' in param_schema:
                    # reduce tokens
                    field_kwargs['description'] = param_schema['description'].split('.')[0]

                param_fields[param_name] = (param_type, Field(default, **field_kwargs))

        # Create Pydantic model for the tool parameters
        if param_fields:
            # Create a BaseModel class with proper configuration
            class ConfiguredBaseModel(BaseModel):
                model_config = ConfigDict(extra='forbid', validate_by_name=True, validate_by_alias=True)

            param_model = create_model(f'{action_name}_Params', __base__=ConfiguredBaseModel, **param_fields)
        else:
            # No parameters - create empty model
            param_model = None

        # Create async wrapper function for the Composio tool
        if param_model:
            # Function takes param model as first parameter
            async def composio_action_wrapper(params: param_model) -> ActionResult:  # type: ignore[no-redef]
                """Wrapper function that calls the Composio tool."""
                if not self.composio_instance:
                    return ActionResult(error=f"Composio instance not available", success=False)

                # Convert pydantic model to dict for Composio call
                tool_params = params.model_dump(exclude_none=True)

                logger.debug(f"🔧 Calling Composio tool '{tool_name}' with params: {tool_params}")

                start_time = time.time()
                error_msg = None

                try:
                    # Call the Composio tool using the tools.execute method
                    entity_id = "default"  # Use default entity ID
                    if 'include_payload' in tool_params:
                        tool_params['include_payload'] = False
                    result = self.composio_instance.tools.execute(
                        slug=tool_name,
                        arguments=tool_params,
                        user_id=entity_id,
                    )

                    # Convert Composio result to ActionResult
                    extracted_content = self._format_composio_result(result)

                    return ActionResult(
                        extracted_content=extracted_content,
                        long_term_memory=f"Used Composio tool '{tool_name}' from {toolkit_slug}",
                    )

                except Exception as e:
                    error_msg = f"Composio tool '{tool_name}' failed: {str(e)}"
                    logger.error(error_msg)
                    return ActionResult(error=error_msg, success=False)
                finally:
                    # Log execution time and capture telemetry
                    duration = time.time() - start_time
                    logger.debug(f"Composio tool '{tool_name}' executed in {duration:.2f}s")
                    
                    # Capture telemetry for tool call
                    self._telemetry.capture(
                        ComposioTelemetryEvent(
                            toolkit_slugs=[toolkit_slug],
                            tools_registered=len(self._registered_actions),
                            version=get_vibesurf_version(),
                            action='tool_call',
                            toolkit_slug=toolkit_slug,
                            tool_name=tool_name,
                            duration_seconds=duration,
                            error_message=error_msg
                        )
                    )
        else:
            # No parameters - empty function signature
            async def composio_action_wrapper() -> ActionResult:  # type: ignore[no-redef]
                """Wrapper function that calls the Composio tool."""
                if not self.composio_instance:
                    return ActionResult(error=f"Composio instance not available", success=False)

                logger.debug(f"🔧 Calling Composio tool '{tool_name}' with no params")

                start_time = time.time()
                error_msg = None

                try:
                    # Call the Composio tool with empty params
                    entity_id = "default"  # Use default entity ID
                    result = self.composio_instance.tools.execute(
                        slug=tool_name,
                        arguments={},
                        user_id=entity_id,
                    )

                    # Convert Composio result to ActionResult
                    extracted_content = self._format_composio_result(result)

                    return ActionResult(
                        extracted_content=extracted_content,
                        long_term_memory=f"Used Composio tool '{tool_name}' from {toolkit_slug}",
                    )

                except Exception as e:
                    error_msg = f"Composio tool '{tool_name}' failed: {str(e)}"
                    logger.error(error_msg)
                    return ActionResult(error=error_msg, success=False)
                finally:
                    # Log execution time and capture telemetry
                    duration = time.time() - start_time
                    logger.debug(f"Composio tool '{tool_name}' executed in {duration:.2f}s")
                    
                    # Capture telemetry for tool call
                    self._telemetry.capture(
                        ComposioTelemetryEvent(
                            toolkit_slugs=[toolkit_slug],
                            tools_registered=len(self._registered_actions),
                            version=get_vibesurf_version(),
                            action='tool_call',
                            toolkit_slug=toolkit_slug,
                            tool_name=tool_name,
                            duration_seconds=duration,
                            error_message=error_msg
                        )
                    )

        # Set function metadata for better debugging
        composio_action_wrapper.__name__ = action_name
        composio_action_wrapper.__qualname__ = f'composio.{toolkit_slug}.{action_name}'

        # Register the action with VibeSurf
        registry.action(description=description, param_model=param_model)(composio_action_wrapper)

        logger.debug(f"✅ Registered Composio tool '{tool_name}' as action '{action_name}'")

    def _format_composio_result(self, result: Any) -> str:
        """Format Composio tool result into a string for ActionResult.

        Args:
            result: Raw result from Composio tool call

        Returns:
            Formatted string representation of the result
        """
        # Handle different Composio result formats
        if isinstance(result, dict) or isinstance(result, list):
            # Dictionary result
            try:
                return f"```json\n{json.dumps(result, indent=2, ensure_ascii=False)}\n```"
            except (TypeError, ValueError):
                return str(result)
        else:
            # Direct result or unknown format
            return str(result)

    def _json_schema_to_python_type(self, schema: dict, model_name: str = 'NestedModel') -> Any:
        """Convert JSON Schema type to Python type.

        Args:
            schema: JSON Schema definition
            model_name: Name for nested models

        Returns:
            Python type corresponding to the schema
        """
        json_type = schema.get('type', 'string')

        # Basic type mapping
        type_mapping = {
            'string': str,
            'number': float,
            'integer': int,
            'boolean': bool,
            'array': list,
            'null': type(None),
        }

        # Handle enums (they're still strings)
        if 'enum' in schema:
            return str

        # Handle objects with nested properties
        if json_type == 'object':
            properties = schema.get('properties', {})
            if properties:
                # Create nested pydantic model for objects with properties
                nested_fields = {}
                required_fields = set(schema.get('required', []))

                for prop_name, prop_schema in properties.items():
                    # Recursively process nested properties
                    prop_type = self._json_schema_to_python_type(prop_schema, f'{model_name}_{prop_name}')

                    # Determine if field is required and handle defaults
                    if prop_name in required_fields:
                        default = ...  # Required field
                    else:
                        # Optional field - make type optional and handle default
                        prop_type = prop_type | None
                        if 'default' in prop_schema:
                            default = prop_schema['default']
                        else:
                            default = None

                    # Add field with description if available
                    field_kwargs = {}
                    if 'description' in prop_schema:
                        field_kwargs['description'] = prop_schema['description']

                    nested_fields[prop_name] = (prop_type, Field(default, **field_kwargs))

                # Create a BaseModel class with proper configuration
                class ConfiguredBaseModel(BaseModel):
                    model_config = ConfigDict(extra='forbid', validate_by_name=True, validate_by_alias=True)

                try:
                    # Create and return nested pydantic model
                    return create_model(model_name, __base__=ConfiguredBaseModel, **nested_fields)
                except Exception as e:
                    logger.error(f'Failed to create nested model {model_name}: {e}')
                    logger.debug(f'Fields: {nested_fields}')
                    # Fallback to basic dict if model creation fails
                    return dict
            else:
                # Object without properties - just return dict
                return dict

        # Handle arrays with specific item types
        if json_type == 'array':
            if 'items' in schema:
                # Get the item type recursively
                item_type = self._json_schema_to_python_type(schema['items'], f'{model_name}_item')
                # Return properly typed list
                return list[item_type]
            else:
                # Array without item type specification
                return list

        # Get base type for non-object types
        base_type = type_mapping.get(json_type, str)

        # Handle nullable/optional types
        if schema.get('nullable', False) or json_type == 'null':
            return base_type | None

        return base_type

    def unregister_all_tools(self, tools):
        """Unregister all Composio tools from the registry"""
        try:
            # Get all registered actions
            actions_to_remove = []
            for action_name in list(tools.registry.registry.actions.keys()):
                if action_name.startswith('cpo.'):
                    actions_to_remove.append(action_name)

            # Remove Composio actions from registry
            for action_name in actions_to_remove:
                if action_name in tools.registry.registry.actions:
                    del tools.registry.registry.actions[action_name]
                    logger.debug(f'Removed Composio action: {action_name}')

            # Clear the registered actions set
            self._registered_actions.clear()
            self._toolkit_tools.clear()
            
            logger.info(f"Unregistered {len(actions_to_remove)} Composio actions")
            
            # Capture telemetry for unregistration
            self._telemetry.capture(
                ComposioTelemetryEvent(
                    toolkit_slugs=list(self._toolkit_tools.keys()),
                    tools_registered=0,  # All tools unregistered
                    version=get_vibesurf_version(),
                    action='unregister'
                )
            )
            self._telemetry.flush()

        except Exception as e:
            error_msg = str(e)
            logger.error(f'Failed to unregister Composio actions: {error_msg}')
            
            # Capture telemetry for unregistration error
            self._telemetry.capture(
                ComposioTelemetryEvent(
                    toolkit_slugs=list(self._toolkit_tools.keys()),
                    tools_registered=len(self._registered_actions),
                    version=get_vibesurf_version(),
                    action='unregister',
                    error_message=error_msg
                )
            )
            self._telemetry.flush()