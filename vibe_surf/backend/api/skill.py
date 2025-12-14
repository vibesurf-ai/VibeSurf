"""
Workflow Skill API
Handles workflow skill configuration for exposing workflow inputs as skills
"""
from typing import Optional, Dict, Any, List
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.manager import get_db_session
from ..database.queries import WorkflowSkillQueries
from vibe_surf.langflow.services.deps import session_scope, get_settings_service
from vibe_surf.langflow.services.auth.utils import create_super_user
from vibe_surf.langflow.api.v1.flows import _read_flow
from vibe_surf.logger import get_logger

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/skill", tags=["skill"])

# Request/Response models
class WorkflowExposeConfigRequest(BaseModel):
    flow_id: str
    add_to_skill: bool
    workflow_expose_config: Optional[Dict[str, Any]] = None

class WorkflowExposeConfigResponse(BaseModel):
    success: bool
    message: str
    flow_id: str
    add_to_skill: bool
    workflow_expose_config: Optional[Dict[str, Any]] = None

class GetWorkflowExposeConfigResponse(BaseModel):
    success: bool
    flow_id: str
    add_to_skill: bool
    workflow_expose_config: Dict[str, Any]


def extract_exposable_inputs(workflow_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract exposable inputs from workflow data based on rules:
    1. Input name cannot start with underscore
    2. Exclude 'code' input
    3. Input must not be connected (no edge connection)
    4. Type cannot be 'HandleInput'
    5. ChatInput's input_value is exposed by default
    
    Returns a dict with component_id as key and exposable inputs info
    """
    workflow_expose_config = {}
    
    try:
        data = workflow_data.get("data", {})
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        
        # Build a set of connected input fields for quick lookup
        connected_inputs = set()
        for edge in edges:
            edge_data = edge.get("data", {})
            target_handle = edge_data.get("targetHandle", {})
            
            if isinstance(target_handle, dict):
                target_id = target_handle.get("id")
                field_name = target_handle.get("fieldName")
                if target_id and field_name:
                    connected_inputs.add(f"{target_id}:{field_name}")
            elif isinstance(target_handle, str):
                # Handle string format like '{"fieldName":"query","id":"AdvancedSearchComponent-aHkjr",...}'
                import json
                try:
                    # Replace special character (œ) with proper quotes
                    target_handle_str = target_handle.replace('œ', '"')
                    target_handle_dict = json.loads(target_handle_str)
                    target_id = target_handle_dict.get("id")
                    field_name = target_handle_dict.get("fieldName")
                    if target_id and field_name:
                        connected_inputs.add(f"{target_id}:{field_name}")
                except:
                    pass
        
        # Process each node
        for node in nodes:
            node_data = node.get("data", {})
            node_info = node_data.get("node", {})
            template = node_info.get("template", {})
            
            component_id = node_data.get("id")
            component_type = node.get("type", "")
            display_name = node_info.get("display_name", component_id)
            
            if not component_id:
                continue
            
            exposable_inputs = {}
            
            # Process each input field in template
            for field_name, field_config in template.items():
                if not isinstance(field_config, dict):
                    continue
                
                # Rule 1: Skip if field name starts with underscore
                if field_name.startswith("_"):
                    continue
                
                # Rule 2: Skip 'code' input
                if field_name == "code":
                    continue
                
                # Rule 4: Skip HandleInput type
                input_type = field_config.get("_input_type") or field_config.get("type")
                if input_type == "HandleInput":
                    continue
                
                # Rule 3: Skip if connected
                connection_key = f"{component_id}:{field_name}"
                if connection_key in connected_inputs:
                    continue
                
                # Rule 5: ChatInput's input_value is exposed by default
                is_exposed = (component_type == "ChatInput" and field_name == "input_value")
                
                # Extract relevant field information
                exposable_inputs[field_name] = {
                    "display_name": field_config.get("display_name", field_name),
                    "type": field_config.get("type", "str"),
                    "info": field_config.get("info", ""),
                    "required": field_config.get("required", False),
                    "value": field_config.get("value"),
                    "is_expose": is_exposed
                }
            
            # Only add component if it has exposable inputs
            if exposable_inputs:
                workflow_expose_config[component_id] = {
                    "component_name": display_name,
                    "component_type": component_type,
                    "inputs": exposable_inputs
                }
        
        return workflow_expose_config
        
    except Exception as e:
        logger.error(f"Error extracting exposable inputs: {e}")
        import traceback
        traceback.print_exc()
        return {}


@router.get("/workflow-expose-config/{flow_id}", response_model=GetWorkflowExposeConfigResponse)
async def get_workflow_expose_config(
    flow_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get workflow expose configuration for a flow.
    If not exists in DB, generate from workflow data.
    If exists in DB, merge with fresh data from workflow.
    """
    try:
        # Convert flow_id to UUID
        try:
            flow_uuid = UUID(flow_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid flow ID format")
        
        # Get settings for authentication
        settings_service = get_settings_service()
        username = settings_service.auth_settings.SUPERUSER
        password = settings_service.auth_settings.SUPERUSER_PASSWORD
        
        # Fetch workflow from langflow database using session_scope
        async with session_scope() as langflow_session:
            current_user = await create_super_user(db=langflow_session, username=username, password=password)
            db_flow = await _read_flow(session=langflow_session, flow_id=flow_uuid, user_id=current_user.id)
            
            if not db_flow:
                raise HTTPException(status_code=404, detail=f"Workflow not found: {flow_id}")
            
            # Convert to dict to work with existing logic
            workflow_data = {
                "name": db_flow.name,
                "description": db_flow.description,
                "data": db_flow.data
            }
        
        # Extract workflow name and description
        workflow_name = workflow_data.get("name", "")
        workflow_description = workflow_data.get("description", "")
        
        # Extract exposable inputs from workflow data
        fresh_expose_config = extract_exposable_inputs(workflow_data)
        
        # Check if we have existing config in database
        existing_skill = await WorkflowSkillQueries.get_skill(db, flow_id)
        
        if existing_skill and existing_skill.workflow_expose_config:
            # Merge: use database is_expose values, but update with fresh component/field info
            db_config = existing_skill.workflow_expose_config
            
            for component_id, component_data in fresh_expose_config.items():
                if component_id in db_config:
                    # Component exists in DB, merge input configurations
                    db_inputs = db_config[component_id].get("inputs", {})
                    fresh_inputs = component_data.get("inputs", {})
                    
                    for input_name, input_data in fresh_inputs.items():
                        if input_name in db_inputs:
                            # Preserve is_expose from database
                            input_data["is_expose"] = db_inputs[input_name].get("is_expose", False)
            
            # Update database with merged config and workflow info
            await WorkflowSkillQueries.create_or_update_skill(
                db=db,
                flow_id=flow_id,
                name=workflow_name,
                description=workflow_description,
                add_to_skill=existing_skill.add_to_skill,
                workflow_expose_config=fresh_expose_config
            )
            await db.commit()
            
            return GetWorkflowExposeConfigResponse(
                success=True,
                flow_id=flow_id,
                add_to_skill=existing_skill.add_to_skill,
                workflow_expose_config=fresh_expose_config
            )
        else:
            # No existing config, return fresh config with all is_expose=False except ChatInput
            return GetWorkflowExposeConfigResponse(
                success=True,
                flow_id=flow_id,
                add_to_skill=False,
                workflow_expose_config=fresh_expose_config
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workflow expose config: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get workflow expose config: {str(e)}"
        )


@router.post("/workflow-expose-config", response_model=WorkflowExposeConfigResponse)
async def update_workflow_expose_config(
    request: WorkflowExposeConfigRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Update workflow expose configuration.
    If add_to_skill is False, set it to False in database.
    If add_to_skill is True, save the configuration and sync to workflow_skills.
    """
    try:
        # Fetch workflow data to get name and description
        workflow_name = ""
        workflow_description = ""
        
        try:
            # Convert flow_id to UUID
            flow_uuid = UUID(request.flow_id)
            
            # Get settings for authentication
            settings_service = get_settings_service()
            username = settings_service.auth_settings.SUPERUSER
            password = settings_service.auth_settings.SUPERUSER_PASSWORD
            
            # Fetch workflow from langflow database using session_scope
            async with session_scope() as langflow_session:
                current_user = await create_super_user(db=langflow_session, username=username, password=password)
                db_flow = await _read_flow(session=langflow_session, flow_id=flow_uuid, user_id=current_user.id)
                
                if db_flow:
                    workflow_name = db_flow.name or ""
                    workflow_description = db_flow.description or ""
        except Exception as e:
            logger.warning(f"Failed to fetch workflow data for name/description: {e}")
        
        # Create or update skill configuration
        skill_data = await WorkflowSkillQueries.create_or_update_skill(
            db=db,
            flow_id=request.flow_id,
            name=workflow_name,
            description=workflow_description,
            add_to_skill=request.add_to_skill,
            workflow_expose_config=request.workflow_expose_config
        )
        
        await db.commit()
        
        # Sync to shared_state.workflow_skills
        from ..shared_state import workflow_skills
        if request.add_to_skill:
            # Add or update in workflow_skills
            workflow_skills[request.flow_id] = {
                "name": workflow_name,
                "description": workflow_description,
                "workflow_expose_config": request.workflow_expose_config or {}
            }
            logger.info(f"✅ Added workflow {request.flow_id} to workflow_skills")
        else:
            # Remove from workflow_skills if exists
            if request.flow_id in workflow_skills:
                del workflow_skills[request.flow_id]
                logger.info(f"✅ Removed workflow {request.flow_id} from workflow_skills")
        
        return WorkflowExposeConfigResponse(
            success=True,
            message="Workflow skill configuration updated successfully",
            flow_id=request.flow_id,
            add_to_skill=request.add_to_skill,
            workflow_expose_config=request.workflow_expose_config
        )
        
    except Exception as e:
        logger.error(f"Error updating workflow expose config: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update workflow expose config: {str(e)}"
        )


@router.get("/enabled-skills")
async def get_enabled_skills(db: AsyncSession = Depends(get_db_session)):
    """Get all workflows that have add_to_skill enabled"""
    try:
        skills = await WorkflowSkillQueries.list_skills(
            db=db,
            add_to_skill_only=True
        )
        
        result = []
        for skill in skills:
            result.append({
                "flow_id": skill.flow_id,
                "name": skill.name,
                "description": skill.description,
                "workflow_expose_config": skill.workflow_expose_config,
                "created_at": skill.created_at.isoformat() if skill.created_at else None,
                "updated_at": skill.updated_at.isoformat() if skill.updated_at else None
            })
        
        return {
            "success": True,
            "skills": result
        }
        
    except Exception as e:
        logger.error(f"Error getting enabled skills: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get enabled skills: {str(e)}"
        )


@router.get("/workflow-skills")
async def get_workflow_skills():
    """Get all workflow skills from shared state (cached)"""
    try:
        from ..shared_state import workflow_skills
        
        # Format the response similar to @flow-{flow_id[-4:]}: {flow name}
        result = []
        for flow_id, skill_data in workflow_skills.items():
            result.append({
                "flow_id": flow_id,
                "display_name": f"@flow-{flow_id[-4:]}: {skill_data.get('name', flow_id)}",
                "name": skill_data.get("name", ""),
                "description": skill_data.get("description", ""),
                "workflow_expose_config": skill_data.get("workflow_expose_config", {})
            })
        
        return {
            "success": True,
            "workflow_skills": result
        }
        
    except Exception as e:
        logger.error(f"Error getting workflow skills: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get workflow skills: {str(e)}"
        )