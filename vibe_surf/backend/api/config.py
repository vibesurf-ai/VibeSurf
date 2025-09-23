"""
Configuration API endpoints for VibeSurf Backend

Handles LLM Profile and tools configuration management.
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List
import logging

from ..database.manager import get_db_session
from ..database.queries import LLMProfileQueries, McpProfileQueries
from .models import (
    LLMProfileCreateRequest, LLMProfileUpdateRequest, LLMProfileResponse,
    McpProfileCreateRequest, McpProfileUpdateRequest, McpProfileResponse
)

router = APIRouter(prefix="/config", tags=["config"])

from vibe_surf.logger import get_logger

logger = get_logger(__name__)

def _profile_to_response_dict(profile) -> dict:
    """Convert SQLAlchemy LLMProfile to dict for Pydantic validation - safe extraction"""
    try:
        # Use SQLAlchemy's __dict__ to avoid lazy loading issues
        profile_dict = profile.__dict__.copy()
        
        # Remove SQLAlchemy internal keys
        profile_dict.pop('_sa_instance_state', None)
        
        return {
            "profile_id": profile_dict.get("profile_id"),
            "profile_name": profile_dict.get("profile_name"),
            "provider": profile_dict.get("provider"),
            "model": profile_dict.get("model"),
            "base_url": profile_dict.get("base_url"),
            "temperature": profile_dict.get("temperature"),
            "max_tokens": profile_dict.get("max_tokens"),
            "top_p": profile_dict.get("top_p"),
            "frequency_penalty": profile_dict.get("frequency_penalty"),
            "seed": profile_dict.get("seed"),
            "provider_config": profile_dict.get("provider_config"),
            "description": profile_dict.get("description"),
            "is_active": profile_dict.get("is_active"),
            "is_default": profile_dict.get("is_default"),
            "created_at": profile_dict.get("created_at"),
            "updated_at": profile_dict.get("updated_at"),
            "last_used_at": profile_dict.get("last_used_at")
        }
    except Exception as e:
        # Fallback to direct attribute access if __dict__ approach fails
        return {
            "profile_id": str(profile.profile_id),
            "profile_name": str(profile.profile_name),
            "provider": str(profile.provider),
            "model": str(profile.model),
            "base_url": profile.base_url,
            "temperature": profile.temperature,
            "max_tokens": profile.max_tokens,
            "top_p": profile.top_p,
            "frequency_penalty": profile.frequency_penalty,
            "seed": profile.seed,
            "provider_config": profile.provider_config or {},
            "description": profile.description,
            "is_active": bool(profile.is_active),
            "is_default": bool(profile.is_default),
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
            "last_used_at": profile.last_used_at
        }

# LLM Profile Management
@router.post("/llm-profiles", response_model=LLMProfileResponse)
async def create_llm_profile(
    profile_request: LLMProfileCreateRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new LLM profile"""
    try:
        # Check if profile name already exists
        existing_profile = await LLMProfileQueries.get_profile(db, profile_request.profile_name)
        if existing_profile:
            raise HTTPException(
                status_code=400,
                detail=f"Profile with name '{profile_request.profile_name}' already exists"
            )
        
        # Create new profile - now returns dict directly
        profile_data = await LLMProfileQueries.create_profile(
            db=db,
            profile_name=profile_request.profile_name,
            provider=profile_request.provider,
            model=profile_request.model,
            api_key=profile_request.api_key,
            base_url=profile_request.base_url,
            temperature=profile_request.temperature,
            max_tokens=profile_request.max_tokens,
            top_p=profile_request.top_p,
            frequency_penalty=profile_request.frequency_penalty,
            seed=profile_request.seed,
            provider_config=profile_request.provider_config,
            description=profile_request.description,
            is_default=profile_request.is_default
        )
        
        await db.commit()
        
        # If this is set as default, update other profiles
        if profile_request.is_default:
            await LLMProfileQueries.set_default_profile(db, profile_request.profile_name)
            await db.commit()
        
        return LLMProfileResponse(**profile_data)
        
    except Exception as e:
        logger.error(f"Failed to create LLM profile: {e}")
        
        # Handle specific database constraint errors
        error_msg = str(e)
        if "UNIQUE constraint failed: llm_profiles.profile_name" in error_msg:
            raise HTTPException(
                status_code=400,
                detail=f"Profile with name '{profile_request.profile_name}' already exists. Please choose a different name."
            )
        elif "IntegrityError" in error_msg and "profile_name" in error_msg:
            raise HTTPException(
                status_code=400,
                detail=f"Profile name '{profile_request.profile_name}' is already in use. Please choose a different name."
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create LLM profile: {str(e)}"
            )

@router.get("/llm-profiles", response_model=List[LLMProfileResponse])
async def list_llm_profiles(
    active_only: bool = True,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_session)
):
    """List LLM profiles"""
    try:
        profiles = await LLMProfileQueries.list_profiles(
            db=db,
            active_only=active_only,
            limit=limit,
            offset=offset
        )
        
        # Use safe extraction to avoid greenlet issues
        return [LLMProfileResponse(**_profile_to_response_dict(profile)) for profile in profiles]
        
    except Exception as e:
        logger.error(f"Failed to list LLM profiles: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list LLM profiles: {str(e)}"
        )

@router.get("/llm-profiles/{profile_name}", response_model=LLMProfileResponse)
async def get_llm_profile(
    profile_name: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Get specific LLM profile by name"""
    try:
        profile = await LLMProfileQueries.get_profile(db, profile_name)
        if not profile:
            raise HTTPException(
                status_code=404,
                detail=f"LLM profile '{profile_name}' not found"
            )
        
        # Use safe extraction to avoid greenlet issues
        return LLMProfileResponse(**_profile_to_response_dict(profile))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get LLM profile: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get LLM profile: {str(e)}"
        )

@router.put("/llm-profiles/{profile_name}", response_model=LLMProfileResponse)
async def update_llm_profile(
    profile_name: str,
    update_request: LLMProfileUpdateRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Update an existing LLM profile"""
    try:
        # Check if profile exists
        existing_profile = await LLMProfileQueries.get_profile(db, profile_name)
        if not existing_profile:
            raise HTTPException(
                status_code=404,
                detail=f"LLM profile '{profile_name}' not found"
            )
        
        # Prepare update data
        update_data = {}
        for field, value in update_request.model_dump(exclude_unset=True).items():
            if value is not None:
                update_data[field] = value
        
        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="No valid fields provided for update"
            )
        
        # Update profile
        success = await LLMProfileQueries.update_profile(db, profile_name, update_data)
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to update profile"
            )
        
        await db.commit()
        
        # Handle default profile setting
        if update_request.is_default:
            await LLMProfileQueries.set_default_profile(db, profile_name)
            await db.commit()
        
        # Return updated profile
        updated_profile = await LLMProfileQueries.get_profile(db, profile_name)
        from ..shared_state import current_llm_profile_name
        if current_llm_profile_name != profile_name:
            current_llm_profile_name = None
        # Use safe extraction to avoid greenlet issues
        return LLMProfileResponse(**_profile_to_response_dict(updated_profile))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update LLM profile: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update LLM profile: {str(e)}"
        )

@router.delete("/llm-profiles/{profile_name}")
async def delete_llm_profile(
    profile_name: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Delete an LLM profile"""
    try:
        # Check if profile exists
        existing_profile = await LLMProfileQueries.get_profile(db, profile_name)
        if not existing_profile:
            raise HTTPException(
                status_code=404,
                detail=f"LLM profile '{profile_name}' not found"
            )
        
        # Don't allow deletion of default profile
        if existing_profile.is_default:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the default profile. Set another profile as default first."
            )
        
        # TODO: Check if profile is being used by any active tasks
        # This would require checking the tasks table
        
        success = await LLMProfileQueries.delete_profile(db, profile_name)
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete profile"
            )
        
        await db.commit()
        
        return JSONResponse(
            content={"message": f"LLM profile '{profile_name}' deleted successfully"},
            status_code=200
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete LLM profile: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete LLM profile: {str(e)}"
        )

@router.post("/llm-profiles/{profile_name}/set-default")
async def set_default_llm_profile(
    profile_name: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Set an LLM profile as the default"""
    try:
        # Check if profile exists and is active
        profile = await LLMProfileQueries.get_profile(db, profile_name)
        if not profile:
            raise HTTPException(
                status_code=404,
                detail=f"LLM profile '{profile_name}' not found"
            )
        
        if not profile.is_active:
            raise HTTPException(
                status_code=400,
                detail="Cannot set inactive profile as default"
            )
        
        success = await LLMProfileQueries.set_default_profile(db, profile_name)
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to set default profile"
            )
        
        await db.commit()
        
        return JSONResponse(
            content={"message": f"LLM profile '{profile_name}' set as default"},
            status_code=200
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set default LLM profile: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to set default LLM profile: {str(e)}"
        )

@router.get("/llm-profiles/default/current", response_model=LLMProfileResponse)
async def get_default_llm_profile(db: AsyncSession = Depends(get_db_session)):
    """Get the current default LLM profile"""
    try:
        profile = await LLMProfileQueries.get_default_profile(db)
        if not profile:
            raise HTTPException(
                status_code=404,
                detail="No default LLM profile found"
            )
        
        # Use safe extraction to avoid greenlet issues
        return LLMProfileResponse(**_profile_to_response_dict(profile))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get default LLM profile: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get default LLM profile: {str(e)}"
        )

# MCP Profile Management
def _mcp_profile_to_response_dict(profile) -> dict:
    """Convert SQLAlchemy McpProfile to dict for Pydantic validation - safe extraction"""
    try:
        # Use SQLAlchemy's __dict__ to avoid lazy loading issues
        profile_dict = profile.__dict__.copy()
        
        # Remove SQLAlchemy internal keys
        profile_dict.pop('_sa_instance_state', None)
        
        return {
            "mcp_id": profile_dict.get("mcp_id"),
            "display_name": profile_dict.get("display_name"),
            "mcp_server_name": profile_dict.get("mcp_server_name"),
            "mcp_server_params": profile_dict.get("mcp_server_params"),
            "description": profile_dict.get("description"),
            "is_active": profile_dict.get("is_active"),
            "created_at": profile_dict.get("created_at"),
            "updated_at": profile_dict.get("updated_at"),
            "last_used_at": profile_dict.get("last_used_at")
        }
    except Exception as e:
        # Fallback to direct attribute access if __dict__ approach fails
        return {
            "mcp_id": str(profile.mcp_id),
            "display_name": str(profile.display_name),
            "mcp_server_name": str(profile.mcp_server_name),
            "mcp_server_params": profile.mcp_server_params or {},
            "description": profile.description,
            "is_active": bool(profile.is_active),
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
            "last_used_at": profile.last_used_at
        }

@router.post("/mcp-profiles", response_model=McpProfileResponse)
async def create_mcp_profile(
    profile_request: McpProfileCreateRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new MCP profile"""
    try:
        # Check if display name already exists
        existing_profile = await McpProfileQueries.get_profile_by_display_name(db, profile_request.display_name)
        if existing_profile:
            raise HTTPException(
                status_code=400,
                detail=f"MCP Profile with display name '{profile_request.display_name}' already exists"
            )
        
        # Create new profile
        profile_data = await McpProfileQueries.create_profile(
            db=db,
            display_name=profile_request.display_name,
            mcp_server_name=profile_request.mcp_server_name,
            mcp_server_params=profile_request.mcp_server_params,
            description=profile_request.description
        )
        
        await db.commit()
        
        return McpProfileResponse(**profile_data)
        
    except Exception as e:
        logger.error(f"Failed to create MCP profile: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create MCP profile: {str(e)}"
        )

@router.get("/mcp-profiles", response_model=List[McpProfileResponse])
async def list_mcp_profiles(
    active_only: bool = True,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_session)
):
    """List MCP profiles"""
    try:
        profiles = await McpProfileQueries.list_profiles(
            db=db,
            active_only=active_only,
            limit=limit,
            offset=offset
        )
        
        return [McpProfileResponse(**_mcp_profile_to_response_dict(profile)) for profile in profiles]
        
    except Exception as e:
        logger.error(f"Failed to list MCP profiles: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list MCP profiles: {str(e)}"
        )

@router.get("/mcp-profiles/{mcp_id}", response_model=McpProfileResponse)
async def get_mcp_profile(
    mcp_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Get specific MCP profile by ID"""
    try:
        profile = await McpProfileQueries.get_profile(db, mcp_id)
        if not profile:
            raise HTTPException(
                status_code=404,
                detail=f"MCP profile '{mcp_id}' not found"
            )
        
        return McpProfileResponse(**_mcp_profile_to_response_dict(profile))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get MCP profile: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get MCP profile: {str(e)}"
        )

@router.put("/mcp-profiles/{mcp_id}", response_model=McpProfileResponse)
async def update_mcp_profile(
    mcp_id: str,
    update_request: McpProfileUpdateRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Update an existing MCP profile"""
    try:
        logger.info(f"Updating MCP profile {mcp_id}")
        
        # Check if profile exists
        existing_profile = await McpProfileQueries.get_profile(db, mcp_id)
        if not existing_profile:
            raise HTTPException(
                status_code=404,
                detail=f"MCP profile '{mcp_id}' not found"
            )
        
        # Prepare update data
        update_data = {}
        for field, value in update_request.model_dump(exclude_unset=True).items():
            if value is not None:
                update_data[field] = value
        
        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="No valid fields provided for update"
            )
        
        # Update profile
        success = await McpProfileQueries.update_profile(db, mcp_id, update_data)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to update profile"
            )
        
        await db.commit()
        
        # Return updated profile
        updated_profile = await McpProfileQueries.get_profile(db, mcp_id)
        response_data = _mcp_profile_to_response_dict(updated_profile)
        
        return McpProfileResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update MCP profile: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update MCP profile: {str(e)}"
        )

@router.delete("/mcp-profiles/{mcp_id}")
async def delete_mcp_profile(
    mcp_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Delete an MCP profile"""
    try:
        # Check if profile exists
        existing_profile = await McpProfileQueries.get_profile(db, mcp_id)
        if not existing_profile:
            raise HTTPException(
                status_code=404,
                detail=f"MCP profile '{mcp_id}' not found"
            )
        
        # TODO: Check if profile is being used by any active tasks
        # This would require checking the tasks table
        
        success = await McpProfileQueries.delete_profile(db, mcp_id)
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete profile"
            )
        
        await db.commit()
        
        return JSONResponse(
            content={"message": f"MCP profile '{existing_profile.display_name}' deleted successfully"},
            status_code=200
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete MCP profile: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete MCP profile: {str(e)}"
        )

@router.get("/llm/providers")
async def get_available_providers():
    """Get list of available LLM providers"""
    from ..llm_config import get_supported_providers, get_provider_models, get_provider_metadata
    
    providers = []
    for provider_name in get_supported_providers():
        metadata = get_provider_metadata(provider_name)
        models = get_provider_models(provider_name)
        
        provider_info = {
            "name": provider_name,
            "display_name": metadata.get("display_name", provider_name.title()),
            "models": models,
            "model_count": len(models),
            "requires_api_key": metadata.get("requires_api_key", True),
            "supports_base_url": metadata.get("supports_base_url", False),
            "requires_base_url": metadata.get("requires_base_url", False),
            "supports_tools": metadata.get("supports_tools", False),
            "supports_vision": metadata.get("supports_vision", False),
            "default_model": metadata.get("default_model", "")
        }
        
        # Add default base URL if available
        if "default_base_url" in metadata:
            provider_info["default_base_url"] = metadata["default_base_url"]
        if "base_url" in metadata:
            provider_info["base_url"] = metadata["base_url"]
            
        providers.append(provider_info)
    
    return {
        "providers": providers,
        "total_providers": len(providers)
    }

@router.get("/llm/providers/{provider_name}/models")
async def get_provider_models_endpoint(provider_name: str):
    """Get models for a specific LLM provider"""
    from ..llm_config import get_provider_models as get_models, get_provider_metadata, is_provider_supported
    
    if not is_provider_supported(provider_name):
        raise HTTPException(
            status_code=404,
            detail=f"Provider '{provider_name}' not found or not supported"
        )
    
    models = get_models(provider_name)
    metadata = get_provider_metadata(provider_name)
    
    return {
        "provider": provider_name,
        "display_name": metadata.get("display_name", provider_name.title()),
        "models": models,
        "model_count": len(models),
        "default_model": metadata.get("default_model", ""),
        "metadata": metadata
    }

# Configuration status endpoints
@router.get("/status")
async def get_configuration_status(db: AsyncSession = Depends(get_db_session)):
    """Get overall configuration status including LLM profiles"""
    try:
        from .. import shared_state
        
        # Get LLM profiles info
        total_profiles = len(await LLMProfileQueries.list_profiles(db, active_only=False))
        active_profiles = len(await LLMProfileQueries.list_profiles(db, active_only=True))
        default_profile = await LLMProfileQueries.get_default_profile(db)
        
        status = {
            "llm_profiles": {
                "total_profiles": total_profiles,
                "active_profiles": active_profiles,
                "default_profile": default_profile.profile_name if default_profile else None,
                "has_default": default_profile is not None
            },
            "tools": {
                "initialized": shared_state.vibesurf_tools is not None
            },
            "browser_manager": {
                "initialized": shared_state.browser_manager is not None
            },
            "vibesurf_agent": {
                "initialized": shared_state.vibesurf_agent is not None,
                "workspace_dir": shared_state.workspace_dir
            },
            "overall_status": "ready" if (
                    default_profile and
                    shared_state.vibesurf_tools and
                    shared_state.browser_manager and
                    shared_state.vibesurf_agent
            ) else "partial"
        }
        
        return status
        
    except Exception as e:
        logger.error(f"Failed to get configuration status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get configuration status: {str(e)}"
        )

# Environment Variables Management
@router.get("/environments")
async def get_environments():
    """Get current environment variables"""
    try:
        from .. import shared_state
        envs = shared_state.get_envs()
        
        return {
            "environments": envs,
            "count": len(envs)
        }
        
    except Exception as e:
        logger.error(f"Failed to get environments: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get environments: {str(e)}"
        )

@router.put("/environments")
async def update_environments(updates: Dict[str, str]):
    """Update environment variables"""
    try:
        from .. import shared_state
        
        # Validate that we only update allowed keys
        allowed_keys = {
            "BROWSER_EXECUTION_PATH",
            "BROWSER_USER_DATA",
            "VIBESURF_EXTENSION",
            "VIBESURF_BACKEND_URL"
        }
        
        # Filter updates to only include allowed keys
        filtered_updates = {
            key: value for key, value in updates.items()
            if key in allowed_keys
        }
        
        if not filtered_updates:
            raise HTTPException(
                status_code=400,
                detail=f"No valid environment variables provided. Allowed keys: {list(allowed_keys)}"
            )
        
        # Update environment variables
        success = shared_state.update_envs(filtered_updates)
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to update environment variables"
            )
        
        # Return updated environments
        updated_envs = shared_state.get_envs()
        
        return {
            "message": "Environment variables updated successfully",
            "updated_keys": list(filtered_updates.keys()),
            "environments": updated_envs
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update environments: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update environments: {str(e)}"
        )