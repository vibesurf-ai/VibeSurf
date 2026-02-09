"""
Tool API
Provides endpoints for searching, inspecting, and executing actions from vibesurf_tools and browser_use_tools
"""
import json
import os
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from json_repair import repair_json

from vibe_surf.tools.file_system import CustomFileSystem
from vibe_surf.logger import get_logger
from browser_use.agent.views import ActionModel, ActionResult

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/tool", tags=["tool"])


# Request/Response models
class ActionInfo(BaseModel):
    action_name: str
    action_description: str


class SearchActionsResponse(BaseModel):
    success: bool
    total_count: int
    actions: List[ActionInfo]


class ActionParamsResponse(BaseModel):
    success: bool
    action_name: str
    param_schema: Dict[str, Any]


class ExecuteActionRequest(BaseModel):
    action_name: str
    parameters: Dict[str, Any] = {}


class ExecuteActionResponse(BaseModel):
    success: bool
    action_name: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


def _should_filter_action(action_name: str, source: str) -> bool:
    """
    Determine if an action should be filtered out based on filtering rules

    Args:
        action_name: Name of the action
        source: Either 'vibesurf_tools' or 'browser_use_tools'

    Returns:
        True if action should be filtered out, False otherwise
    """
    from ..shared_state import vibesurf_tools, browser_use_tools, workspace_dir
    # Common filtering rules
    if 'done' in action_name.lower():
        return True
    if 'file' in action_name.lower():
        return True
    if 'directory' in action_name.lower():
        return True
    if 'todo' in action_name.lower():
        return True
    
    if action_name.startswith('mcp.') or action_name.startswith('cpo.'):
        return True

    # Specific action filtering
    if action_name == 'execute_python_code':
        return True
    if action_name == 'gen_and_execute_js_code':
        return True
    if action_name == 'screenshot':
        return True

    # Source-specific rules
    if source == 'vibesurf_tools':
        # Filter actions ending with 'agent', except execute_browser_use_agent
        if action_name.endswith('agent') and action_name != 'execute_browser_use_agent':
            return True

    elif source == 'browser_use_tools':
        # Filter actions that exist in vibesurf_tools (duplicates)
        if vibesurf_tools:
            if action_name in vibesurf_tools.registry.registry.actions:
                return True

    return False


def _get_filtered_actions() -> Dict[str, Dict[str, Any]]:
    """
    Get all actions from both vibesurf_tools and browser_use_tools with filtering applied

    Returns:
        Dictionary mapping action_name to action info including source, action object, and original_name
        For browser_use_tools, action_name has "browser." prefix, original_name is without prefix
    """
    from ..shared_state import vibesurf_tools, browser_use_tools, workspace_dir
    filtered_actions = {}

    # Add vibesurf_tools actions
    if vibesurf_tools and hasattr(vibesurf_tools, 'registry'):
        for action_name, action in vibesurf_tools.registry.registry.actions.items():
            if not _should_filter_action(action_name, 'vibesurf_tools'):
                filtered_actions[action_name] = {
                    'source': 'vibesurf_tools',
                    'action': action,
                    'original_name': action_name  # Same as action_name for vibesurf_tools
                }

    # Add browser_use_tools actions with "browser." prefix
    if browser_use_tools and hasattr(browser_use_tools, 'registry'):
        for action_name, action in browser_use_tools.registry.registry.actions.items():
            if not _should_filter_action(action_name, 'browser_use_tools'):
                # Add "browser." prefix for display
                prefixed_name = f"browser.{action_name}"
                filtered_actions[prefixed_name] = {
                    'source': 'browser_use_tools',
                    'action': action,
                    'original_name': action_name  # Store original name without prefix
                }

    return filtered_actions


def _get_action_description(action) -> str:
    """
    Get action description from param_model or return action name
    """
    try:
        return action.description
    except Exception:
        return ''


@router.get("/search", response_model=SearchActionsResponse)
async def search_actions(keyword: Optional[str] = None):
    """
    Search actions by keyword. Returns action names and descriptions.
    If results are fewer than 5, includes parameter schemas.

    Args:
        keyword: Optional search keyword. If empty, returns all actions.

    Returns:
        SearchActionsResponse with matching actions
    """
    try:
        # Get all filtered actions
        all_actions = _get_filtered_actions()

        # Filter by keyword if provided
        if keyword and keyword.strip():
            keyword_lower = keyword.lower()
            matched_actions = {}

            for action_name, action_info in all_actions.items():
                action = action_info['action']
                description = _get_action_description(action)

                # Search in action name and description
                if keyword_lower in action_name.lower() or keyword_lower in description.lower():
                    matched_actions[action_name] = action_info
        else:
            matched_actions = all_actions

        # Build response
        result_actions = []
        include_schemas = len(matched_actions) < 5

        for action_name, action_info in matched_actions.items():
            action = action_info['action']
            description = _get_action_description(action)

            action_result = ActionInfo(
                action_name=action_name,
                action_description=description
            )

            # Include param schema if fewer than 5 results
            # if include_schemas:
            #     try:
            #         param_schema = action.param_model.model_json_schema()
            #         action_result.param_schema = param_schema
            #     except Exception as e:
            #         logger.warning(f"Failed to get param schema for {action_name}: {e}")

            result_actions.append(action_result)

        logger.info(f"🔍 Searched actions with keyword '{keyword}': found {len(result_actions)} actions")

        return SearchActionsResponse(
            success=True,
            total_count=len(result_actions),
            actions=result_actions
        )

    except Exception as e:
        logger.error(f"Error searching actions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to search actions: {str(e)}"
        )


@router.get("/{action_name}/params", response_model=ActionParamsResponse)
async def get_action_params(action_name: str):
    """
    Get parameter schema for a specific action

    Args:
        action_name: Name of the action

    Returns:
        ActionParamsResponse with parameter schema
    """
    try:
        # Get all filtered actions
        all_actions = _get_filtered_actions()

        # Check if action exists
        if action_name not in all_actions:
            raise HTTPException(
                status_code=404,
                detail=f"Action '{action_name}' not found"
            )

        # Get param schema
        action = all_actions[action_name]['action']
        try:
            param_schema = action.param_model.model_json_schema()
        except Exception as e:
            logger.error(f"Failed to get param schema for {action_name}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get parameter schema for action '{action_name}': {str(e)}"
            )

        logger.info(f"ℹ️ Retrieved parameter schema for action: {action_name}")

        return ActionParamsResponse(
            success=True,
            action_name=action_name,
            param_schema=param_schema
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting action params: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get action parameters: {str(e)}"
        )


@router.post("/execute", response_model=ExecuteActionResponse)
async def execute_action(request: ExecuteActionRequest):
    """
    Execute an action with provided parameters

    Args:
        request: ExecuteActionRequest with action_name and action_params

    Returns:
        ExecuteActionResponse with execution result
    """
    from ..shared_state import vibesurf_tools, browser_use_tools, workspace_dir
    try:
        # Get all filtered actions
        all_actions = _get_filtered_actions()

        # Check if action exists
        if request.action_name not in all_actions:
            raise HTTPException(
                status_code=404,
                detail=f"Action '{request.action_name}' not found"
            )

        action_info = all_actions[request.action_name]
        action = action_info['action']
        source = action_info['source']
        original_name = action_info['original_name']  # Get original name without prefix

        # Initialize file_system with workspace_dir + "apis"
        apis_dir = os.path.join(workspace_dir, "apis")
        os.makedirs(apis_dir, exist_ok=True)
        file_system = CustomFileSystem(apis_dir)
        
        if source == "vibesurf_tools":
            ActionModel = vibesurf_tools.registry.create_action_model()
        else:
            ActionModel = browser_use_tools.registry.create_action_model()

        # Validate and create ActionModel
        try:
            if not request.parameters:
                action_dict = {original_name: {}}

                action_model = ActionModel(**action_dict)
            else:
                # Get the parameter model for this action
                param_model = action.param_model

                # Validate parameters using the parameter model
                validated_params = param_model(**request.parameters)
                
                # ActionModel expects a dict with original action_name (without prefix) as key
                action_dict = {original_name: validated_params}

                action_model = ActionModel(**action_dict)

        except Exception as e:
            logger.error(f"Failed to validate parameters for {request.action_name}: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid parameters for action '{request.action_name}': {str(e)}"
            )

        # Execute the action using the act method
        try:
            # Import browser_manager and llm from shared_state
            from ..shared_state import browser_manager, llm, current_llm_profile_name

            # Initialize LLM for this task if needed
            if not current_llm_profile_name:
                return ExecuteActionResponse(
                    success=False,
                    action_name=request.action_name,
                    error="LLM not initialized. Please initialize LLM profile first.",
                    result={"error": "llm_not_initialized"}
                )

            # Execute based on source
            if source == 'vibesurf_tools':
                # vibesurf_tools.act uses: browser_manager, page_extraction_llm, file_system
                result = await vibesurf_tools.act(
                    action=action_model,
                    browser_manager=browser_manager,
                    llm=llm,
                    file_system=file_system
                )
            else:
                # browser_use_tools.act uses: browser_session, page_extraction_llm, file_system
                # Get browser_session from browser_manager.main_browser_session
                active_browser_tab = await browser_manager.get_activate_tab()
                browser_session = browser_manager.main_browser_session
                if active_browser_tab:
                    await browser_session.get_or_create_cdp_session(active_browser_tab.target_id)
                result = await browser_use_tools.act(
                    action=action_model,
                    browser_session=browser_session,
                    page_extraction_llm=llm,
                    file_system=file_system
                )

            # Process result
            if isinstance(result, ActionResult):
                result_dict = {
                    'is_done': getattr(result, 'is_done', False),
                    'success': getattr(result, 'success', True),
                    'extracted_content': getattr(result, 'extracted_content', None),
                    'error': getattr(result, 'error', None),
                    'file_system_base_dir': str(file_system.get_dir()),
                }

                # Check if execution was successful
                if result.error:
                    logger.warning(f"Action {request.action_name} executed with error: {result.error}")
                    return ExecuteActionResponse(
                        success=False,
                        action_name=request.action_name,
                        error=result.error,
                        result=result_dict
                    )
                else:
                    logger.info(f"✅ Successfully executed action: {request.action_name}")
                    return ExecuteActionResponse(
                        success=True,
                        action_name=request.action_name,
                        result=result_dict
                    )
            else:
                logger.warning(f"Unexpected result type from action {request.action_name}: {type(result)}")
                return ExecuteActionResponse(
                    success=True,
                    action_name=request.action_name,
                    result={'raw_result': str(result)}
                )

        except Exception as e:
            logger.error(f"Failed to execute action {request.action_name}: {e}")
            import traceback
            traceback.print_exc()
            return ExecuteActionResponse(
                success=False,
                action_name=request.action_name,
                error=f"Execution failed: {str(e)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing action: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute action: {str(e)}"
        )
