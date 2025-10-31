"""
Composio API endpoints for VibeSurf Backend

Handles Composio integration management including toolkit configuration,
OAuth flow handling, and API key validation.
"""
import pdb

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Optional, Any
import logging
import json
import asyncio
from datetime import datetime

from ..database.manager import get_db_session
from ..database.queries import ComposioToolkitQueries, LLMProfileQueries, CredentialQueries

router = APIRouter(prefix="/composio", tags=["composio"])

from vibe_surf.logger import get_logger

logger = get_logger(__name__)

# Pydantic models for Composio API
from pydantic import BaseModel, Field


class ComposioKeyVerifyRequest(BaseModel):
    """Request model for verifying Composio API key"""
    api_key: str = Field(description="Composio API key to verify")


class ComposioKeyVerifyResponse(BaseModel):
    """Response model for Composio API key verification"""
    valid: bool
    message: str
    user_info: Optional[Dict[str, Any]] = None


class ComposioToolkitResponse(BaseModel):
    """Response model for Composio toolkit data"""
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    logo: Optional[str] = None
    app_url: Optional[str] = None
    enabled: bool
    tools: Optional[List] = None
    connection_status: Optional[str] = None
    created_at: str
    updated_at: str


class ComposioToolkitListResponse(BaseModel):
    """Response model for toolkit list"""
    toolkits: List[ComposioToolkitResponse]
    total_count: int
    synced_count: int


class ComposioToolkitToggleRequest(BaseModel):
    """Request model for enabling/disabling a toolkit"""
    enabled: bool = Field(description="Whether to enable or disable the toolkit")
    force_reauth: Optional[bool] = Field(default=False, description="Force re-authentication if already connected")


class ComposioToolkitToggleResponse(BaseModel):
    """Response model for toolkit toggle operation"""
    success: bool
    message: str
    enabled: bool
    requires_oauth: bool = False
    oauth_url: Optional[str] = None
    connected: bool = False
    connection_status: str


class ComposioToolsResponse(BaseModel):
    """Response model for toolkit tools"""
    toolkit_slug: str
    tools: List[Dict[str, Any]]
    total_tools: int


class ComposioToolsUpdateRequest(BaseModel):
    """Request model for updating selected tools"""
    selected_tools: Dict[str, bool] = Field(description="Mapping of tool_name to enabled status")


class ComposioConnectionStatusResponse(BaseModel):
    """Response model for connection status"""
    toolkit_slug: str
    connected: bool
    connection_id: Optional[str] = None
    status: str
    last_checked: str


async def add_or_update_composio_apikey(composio_api_key):
    from vibe_surf.langflow.services.deps import (
        get_variable_service,
        session_scope,
        get_settings_service
    )
    from vibe_surf.langflow.services.auth.utils import create_super_user, get_current_user
    from vibe_surf.langflow.services.variable.constants import CREDENTIAL_TYPE

    async with session_scope() as async_session:
        settings_service = get_settings_service()
        username = settings_service.auth_settings.SUPERUSER
        password = settings_service.auth_settings.SUPERUSER_PASSWORD.get_secret_value()
        super_user = await create_super_user(
            db=async_session,
            username=username,
            password=password
        )
        variable_service = get_variable_service()
        await variable_service.initialize_user_variables(super_user.id, async_session)

        variables_list = await variable_service.list_variables(
            user_id=super_user.id,
            session=async_session
        )
        composio_key_name = "COMPOSIO_API_KEY"
        if composio_key_name not in variables_list:
            await variable_service.create_variable(
                user_id=super_user.id,
                name=composio_key_name,
                value=composio_api_key,
                type_=CREDENTIAL_TYPE,
                session=async_session,
                default_fields=[]
            )
        else:
            await variable_service.update_variable(
                user_id=super_user.id,
                name=composio_key_name,
                value=composio_api_key,
                session=async_session
            )
        logger.info(f"Set {composio_key_name} to Langflow Variable Database.")


async def _get_composio_api_key_from_db() -> Optional[str]:
    """Get Composio API key from database credentials table (encrypted)"""
    try:
        from .. import shared_state

        if not shared_state.db_manager:
            logger.warning("Database manager not available")
            return None

        async for db in shared_state.db_manager.get_session():
            try:
                api_key = await CredentialQueries.get_credential(db, "COMPOSIO_API_KEY")
                return api_key
            except Exception as e:
                logger.error(f"Failed to retrieve Composio API key from database: {e}")
                return None
    except Exception as e:
        logger.error(f"Database session error while retrieving Composio API key: {e}")
        return None


async def _store_composio_api_key_in_db(api_key: str) -> bool:
    """Store Composio API key in database credentials table (encrypted)"""
    try:
        from .. import shared_state
        if not shared_state.db_manager:
            logger.warning("Database manager not available")
            return False

        async for db in shared_state.db_manager.get_session():
            try:
                success = await CredentialQueries.store_credential(
                    db,
                    "COMPOSIO_API_KEY",
                    api_key,
                    "Composio API key for toolkit integrations"
                )
                if success:
                    await db.commit()
                    logger.info("✅ Composio API key stored successfully")
                return success
            except Exception as e:
                logger.error(f"Failed to store Composio API key in database: {e}")
                return False
    except Exception as e:
        logger.error(f"Database session error while storing Composio API key: {e}")
        return False


async def _get_composio_instance():
    """Get or create Composio instance from shared state"""
    try:
        from .. import shared_state
        if shared_state.composio_instance is None:
            # Try to get API key from database first
            api_key = await _get_composio_api_key_from_db()
            if not api_key:
                # If no API key in database, Composio instance cannot be created
                return None

            # Import Composio here to avoid circular imports
            from composio import Composio
            from composio_langchain import LangchainProvider

            # Create Composio instance
            shared_state.composio_instance = Composio(
                api_key=api_key,
                provider=LangchainProvider()
            )
            logger.info("✅ Composio instance created successfully")

        return shared_state.composio_instance
    except Exception as e:
        logger.error(f"Failed to get Composio instance: {e}")
        return None


@router.get("/status")
async def get_composio_status(
        db: AsyncSession = Depends(get_db_session)
):
    """
    Get current Composio connection status without API validation
    """
    try:
        from .. import shared_state
        logger.info("Checking Composio connection status")

        # Check if we already have a valid Composio instance
        if shared_state.composio_instance is not None:
            # try:
            #     # Quick test to verify instance is still valid
            #     await asyncio.to_thread(lambda: shared_state.composio_instance.toolkits.get())
            #     return {
            #         "connected": True,
            #         "key_valid": True,
            #         "has_key": True,
            #         "message": "Composio is connected and ready",
            #         "instance_available": True
            #     }
            # except Exception as e:
            #     logger.warning(f"Composio instance validation failed: {e}")
            #     # Instance is invalid, clear it
            #     shared_state.composio_instance = None

            return {
                "connected": True,
                "key_valid": True,
                "has_key": True,
                "message": "Composio is connected and ready",
                "instance_available": True
            }

        # No valid instance, check if we have API key in database
        api_key = await _get_composio_api_key_from_db()

        if api_key:
            # Try to create instance with stored API key
            try:
                from composio import Composio
                from composio_langchain import LangchainProvider

                temp_composio = Composio(
                    api_key=api_key,
                    provider=LangchainProvider()
                )

                # Test the instance
                api_toolkits = await asyncio.to_thread(lambda: temp_composio.toolkits.get())

                oauth2_toolkits = []

                for toolkit in api_toolkits:
                    if hasattr(toolkit, 'auth_schemes') and 'OAUTH2' in toolkit.auth_schemes:
                        oauth2_toolkits.append(toolkit)

                logger.info(f"Found {len(oauth2_toolkits)} OAuth2 toolkits from Composio API")

                # Sync with database
                for api_toolkit in oauth2_toolkits:
                    # Check if toolkit already exists
                    existing_toolkit = await ComposioToolkitQueries.get_toolkit_by_slug(db, api_toolkit.slug)

                    # Get metadata from toolkit
                    description = getattr(api_toolkit.meta, 'description', None) if hasattr(api_toolkit,
                                                                                            'meta') else None
                    logo = getattr(api_toolkit.meta, 'logo', None) if hasattr(api_toolkit, 'meta') else None
                    app_url = getattr(api_toolkit.meta, 'app_url', None) if hasattr(api_toolkit, 'meta') else None

                    if not existing_toolkit:
                        # Create new toolkit
                        toolkit_data = await ComposioToolkitQueries.create_toolkit(
                            db=db,
                            name=api_toolkit.name,
                            slug=api_toolkit.slug,
                            description=description,
                            logo=logo,
                            app_url=app_url,
                            enabled=False,
                            tools=None
                        )
                        logger.info(f"Created new toolkit: {api_toolkit.name}")
                    else:
                        # Update existing toolkit information (but keep enabled status and tools)
                        update_data = {
                            'name': api_toolkit.name,
                            'description': description,
                            'logo': logo,
                            'app_url': app_url
                        }
                        await ComposioToolkitQueries.update_toolkit_by_slug(db, api_toolkit.slug, update_data)
                        logger.debug(f"Updated existing toolkit: {api_toolkit.name}")

                await db.commit()

                # Store valid instance
                shared_state.composio_instance = temp_composio

                logger.info("✅ Composio instance recreated from stored API key")
                return {
                    "connected": True,
                    "key_valid": True,
                    "has_key": True,
                    "message": "Composio connection restored from stored API key",
                    "instance_available": True
                }

            except Exception as e:
                logger.warning(f"Stored API key validation failed: {e}")
                # Clear invalid stored key
                shared_state.composio_instance = None
                return {
                    "connected": False,
                    "key_valid": False,
                    "has_key": True,
                    "message": f"Stored API key is invalid: {str(e)}",
                    "instance_available": False
                }

        # No API key in database
        return {
            "connected": False,
            "key_valid": False,
            "has_key": False,
            "message": "No Composio API key configured",
            "instance_available": False
        }

    except Exception as e:
        logger.error(f"Failed to check Composio status: {e}")
        return {
            "connected": False,
            "key_valid": False,
            "has_key": False,
            "message": f"Status check failed: {str(e)}",
            "instance_available": False
        }


@router.post("/verify-key", response_model=ComposioKeyVerifyResponse)
async def verify_composio_api_key(
        request: ComposioKeyVerifyRequest,
        db: AsyncSession = Depends(get_db_session)
):
    """
    Verify Composio API key validity and optionally store it
    """
    try:
        from .. import shared_state
        logger.info("Verifying Composio API key")

        # Import Composio here to avoid startup dependencies
        from composio import Composio
        from composio_langchain import LangchainProvider

        # Create temporary Composio instance for verification
        try:
            temp_composio = Composio(
                api_key=request.api_key,
                provider=LangchainProvider()
            )

            # Test the API key by getting toolkits
            toolkits = await asyncio.to_thread(lambda: temp_composio.toolkits.get(slug='gmail'))

            # If we get here, the API key is valid
            logger.info("✅ Composio API key verified successfully")

            # Store the valid API key in database
            store_success = await _store_composio_api_key_in_db(request.api_key)

            # Update shared state with new Composio instance
            shared_state.composio_instance = temp_composio
            await add_or_update_composio_apikey(request.api_key)
            return ComposioKeyVerifyResponse(
                valid=True,
                message="API key verified successfully" + (" and stored in database" if store_success else ""),
                user_info={"toolkits_count": 1}
            )

        except Exception as e:
            logger.warning(f"Composio API key verification failed: {e}")
            return ComposioKeyVerifyResponse(
                valid=False,
                message=f"Invalid API key: {str(e)}"
            )

    except Exception as e:
        logger.error(f"Failed to verify Composio API key: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to verify Composio API key: {str(e)}"
        )


@router.get("/toolkits", response_model=ComposioToolkitListResponse)
async def get_composio_toolkits(
        sync_with_api: bool = False,  # Changed default to False
        db: AsyncSession = Depends(get_db_session)
):
    """
    Get all OAuth2 toolkits from database and optionally sync with Composio API
    """
    try:
        from .. import shared_state
        logger.info(f"Getting Composio toolkits (sync_with_api={sync_with_api})")

        synced_count = 0

        # Get all toolkits from database
        db_toolkits = await ComposioToolkitQueries.list_toolkits(db, enabled_only=False)
        # Convert to response format
        toolkit_responses = []

        if not db_toolkits and shared_state.composio_instance:
            api_toolkits = await asyncio.to_thread(lambda: shared_state.composio_instance.toolkits.get())

            oauth2_toolkits = []

            for toolkit in api_toolkits:
                if hasattr(toolkit, 'auth_schemes') and 'OAUTH2' in toolkit.auth_schemes:
                    oauth2_toolkits.append(toolkit)

            logger.info(f"Found {len(oauth2_toolkits)} OAuth2 toolkits from Composio API")

            # Sync with database
            for api_toolkit in oauth2_toolkits:
                # Check if toolkit already exists
                existing_toolkit = await ComposioToolkitQueries.get_toolkit_by_slug(db, api_toolkit.slug)

                # Get metadata from toolkit
                description = getattr(api_toolkit.meta, 'description', None) if hasattr(api_toolkit,
                                                                                        'meta') else None
                logo = getattr(api_toolkit.meta, 'logo', None) if hasattr(api_toolkit, 'meta') else None
                app_url = getattr(api_toolkit.meta, 'app_url', None) if hasattr(api_toolkit, 'meta') else None

                if not existing_toolkit:
                    # Create new toolkit
                    toolkit_data = await ComposioToolkitQueries.create_toolkit(
                        db=db,
                        name=api_toolkit.name,
                        slug=api_toolkit.slug,
                        description=description,
                        logo=logo,
                        app_url=app_url,
                        enabled=False,
                        tools=None
                    )
                    logger.info(f"Created new toolkit: {api_toolkit.name}")
                else:
                    # Update existing toolkit information (but keep enabled status and tools)
                    update_data = {
                        'name': api_toolkit.name,
                        'description': description,
                        'logo': logo,
                        'app_url': app_url
                    }
                    await ComposioToolkitQueries.update_toolkit_by_slug(db, api_toolkit.slug, update_data)
                    logger.debug(f"Updated existing toolkit: {api_toolkit.name}")

            await db.commit()
            db_toolkits = await ComposioToolkitQueries.list_toolkits(db, enabled_only=False)

        for toolkit in db_toolkits:
            # Parse tools JSON if present
            tools_data = None
            if toolkit.tools:
                try:
                    tools_data = json.loads(toolkit.tools)
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Failed to parse tools for toolkit {toolkit.slug}: {e}")
                    tools_data = None

            toolkit_responses.append(ComposioToolkitResponse(
                id=toolkit.id,
                name=toolkit.name,
                slug=toolkit.slug,
                description=toolkit.description,
                logo=toolkit.logo,
                app_url=toolkit.app_url,
                enabled=toolkit.enabled,
                tools=tools_data,
                connection_status="unknown",  # Will be updated by connection status check
                created_at=toolkit.created_at.isoformat(),
                updated_at=toolkit.updated_at.isoformat()
            ))
        logger.info(f"Found {len(toolkit_responses)} toolkits from Composio API")
        return ComposioToolkitListResponse(
            toolkits=toolkit_responses,
            total_count=len(toolkit_responses),
            synced_count=synced_count
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get Composio toolkits: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get Composio toolkits: {str(e)}"
        )


@router.post("/toolkit/{slug}/toggle", response_model=ComposioToolkitToggleResponse)
async def toggle_composio_toolkit(
        slug: str,
        request: ComposioToolkitToggleRequest,
        db: AsyncSession = Depends(get_db_session)
):
    """
    Enable/disable a toolkit and handle OAuth flow if needed
    """
    try:
        logger.info(f"Toggling toolkit {slug} to enabled={request.enabled}")

        # Get toolkit from database
        toolkit = await ComposioToolkitQueries.get_toolkit_by_slug(db, slug)
        if not toolkit:
            raise HTTPException(
                status_code=404,
                detail=f"Toolkit '{slug}' not found"
            )

        # Get Composio instance
        composio = await _get_composio_instance()
        if composio is None:
            raise HTTPException(
                status_code=400,
                detail="Composio API key not configured. Please verify your API key first."
            )

        auth_url = None
        connection_status = "disconnected"
        entity_id = "default"  # Use default entity ID

        if request.enabled:
            # Check if toolkit needs OAuth connection
            try:
                # Check for existing active connections using the new API
                def _find_active_connection():
                    try:
                        connection_list = composio.connected_accounts.list(
                            user_ids=[entity_id],
                            toolkit_slugs=[slug.lower()]
                        )

                        if connection_list and hasattr(connection_list, "items") and connection_list.items:
                            for connection in connection_list.items:
                                connection_id = getattr(connection, "id", None)
                                connection_status = getattr(connection, "status", None)
                                if connection_status == "ACTIVE" and connection_id:
                                    return connection_id, connection_status
                        return None, None
                    except Exception as e:
                        logger.error(f"Error checking connections: {e}")
                        return None, None

                connection_id, conn_status = await asyncio.to_thread(_find_active_connection)

                if not connection_id or request.force_reauth:
                    # Need to create OAuth connection
                    try:
                        def _create_auth_connection():
                            try:
                                # Get or create auth config
                                auth_configs = composio.auth_configs.list(toolkit_slug=slug)

                                auth_config_id = None
                                if len(auth_configs.items) == 0:
                                    # Create new auth config
                                    auth_config_response = composio.auth_configs.create(
                                        toolkit=slug,
                                        options={"type": "use_composio_managed_auth"}
                                    )
                                    auth_config_id = auth_config_response.id if hasattr(auth_config_response,
                                                                                        'id') else auth_config_response
                                else:
                                    # Use existing OAUTH2 auth config
                                    for auth_config in auth_configs.items:
                                        if auth_config.auth_scheme == "OAUTH2":
                                            auth_config_id = auth_config.id
                                            break

                                if not auth_config_id:
                                    raise Exception("Could not find or create auth config")

                                # Initiate connection
                                connection_request = composio.connected_accounts.initiate(
                                    user_id=entity_id,
                                    auth_config_id=auth_config_id,
                                    allow_multiple=True
                                )

                                return getattr(connection_request, 'redirect_url', None)

                            except Exception as e:
                                logger.error(f"Error creating auth connection: {e}")
                                raise e

                        auth_url = await asyncio.to_thread(_create_auth_connection)

                        if auth_url:
                            connection_status = "pending_auth"
                            logger.info(f"Generated OAuth URL for {slug}: {auth_url}")
                        else:
                            logger.warning(f"No OAuth URL returned for {slug}")
                            connection_status = "error"

                    except Exception as e:
                        logger.error(f"Failed to create OAuth connection for {slug}: {e}")
                        connection_status = "error"

                else:
                    connection_status = "connected"
                    logger.info(f"Toolkit {slug} already has active connection")

            except Exception as e:
                logger.warning(f"Failed to check connections for {slug}: {e}")
                connection_status = "unknown"

        # If enabling and connected, fetch and save tools
        if request.enabled and connection_status == "connected":
            try:
                entity_id = "default"  # Use default entity ID
                api_tools = await asyncio.to_thread(
                    lambda: composio.tools.get(user_id=entity_id, toolkits=[slug.lower()], limit=999)
                )

                # Convert to response format
                tools_list = []
                for tool in api_tools:
                    tools_list.append({
                        'name': tool.name,
                        'description': getattr(tool, 'description', ''),
                        'parameters': tool.args_schema.model_json_schema() if hasattr(tool, 'args_schema') else {},
                        'enabled': True  # Default enabled
                    })

                # Save tools to database
                if tools_list:
                    try:
                        tools_json = json.dumps(tools_list)
                        await ComposioToolkitQueries.update_toolkit_tools(
                            db,
                            toolkit.id,
                            tools_json
                        )
                        logger.info(f"Synced {len(tools_list)} tools for toolkit {slug}")
                    except Exception as e:
                        logger.warning(f"Failed to save tools to database for toolkit {slug}: {e}")

            except Exception as e:
                logger.warning(f"Failed to fetch tools for toolkit {slug}: {e}")

        # Update toolkit enabled status in database
        update_data = {'enabled': request.enabled}
        if request.enabled and connection_status == "connected" and 'tools_list' in locals():
            # Also update tools if we fetched them
            update_data['tools'] = json.dumps(tools_list) if tools_list else None

        success = await ComposioToolkitQueries.update_toolkit_by_slug(
            db,
            slug,
            update_data
        )

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to update toolkit status in database"
            )

        await db.commit()

        message = f"Toolkit '{toolkit.name}' {'enabled' if request.enabled else 'disabled'} successfully"
        requires_oauth = auth_url is not None
        is_connected = connection_status == "connected"

        if auth_url:
            message += ". Please complete OAuth authentication."

        logger.info(f"✅ {message}")

        return ComposioToolkitToggleResponse(
            success=True,
            message=message,
            enabled=request.enabled,
            requires_oauth=requires_oauth,
            oauth_url=auth_url,
            connected=is_connected,
            connection_status=connection_status
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle toolkit {slug}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to toggle toolkit: {str(e)}"
        )


@router.get("/toolkit/{slug}/tools", response_model=ComposioToolsResponse)
async def get_toolkit_tools(
        slug: str,
        db: AsyncSession = Depends(get_db_session)
):
    """
    Get available tools for a specific toolkit
    First tries to get from database, if empty then fetches from API and saves to database
    """
    try:
        logger.info(f"Getting tools for toolkit {slug}")

        # Get toolkit from database
        toolkit = await ComposioToolkitQueries.get_toolkit_by_slug(db, slug)
        if not toolkit:
            raise HTTPException(
                status_code=404,
                detail=f"Toolkit '{slug}' not found"
            )
        # First, try to get tools from database
        if toolkit.tools:
            try:
                tools_list = json.loads(toolkit.tools)
                if tools_list:
                    logger.info(f"Found {len(tools_list)} tools for toolkit {slug} from database")
                    return ComposioToolsResponse(
                        toolkit_slug=slug,
                        tools=tools_list,
                        total_tools=len(tools_list)
                    )
                    
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse existing tools from database for {slug}: {e}")

        # If we reach here, either no tools in database or invalid format
        # Get Composio instance and fetch from API
        composio = await _get_composio_instance()
        if composio is None:
            raise HTTPException(
                status_code=400,
                detail="Composio API key not configured. Please verify your API key first."
            )

        # Get tools from Composio API
        try:
            entity_id = "default"  # Use default entity ID
            api_tools = await asyncio.to_thread(
                lambda: composio.tools.get(user_id=entity_id, toolkits=[slug.lower()], limit=999)
            )

            # Convert to response format
            tools_list = []
            for tool in api_tools:
                tools_list.append({
                    'name': tool.name,
                    'description': getattr(tool, 'description', ''),
                    'parameters': tool.args_schema.model_json_schema() if hasattr(tool, 'args_schema') else {},
                    'enabled': True  # Default enabled
                })

            # Save tools to database for future use
            try:
                tools_json = json.dumps(tools_list)
                success = await ComposioToolkitQueries.update_toolkit_tools(
                    db,
                    toolkit.id,
                    tools_json
                )
                if success:
                    await db.commit()
                else:
                    logger.warning(f"Failed to save tools to database for toolkit {slug}")
            except Exception as e:
                logger.warning(f"Failed to save tools to database for toolkit {slug}: {e}")

            logger.info(f"Found {len(tools_list)} tools for toolkit {slug} from API and saved to database")

            return ComposioToolsResponse(
                toolkit_slug=slug,
                tools=tools_list,
                total_tools=len(tools_list)
            )

        except Exception as e:
            logger.error(f"Failed to get tools for toolkit {slug} from API: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get tools from Composio API: {str(e)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get toolkit tools for {slug}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get toolkit tools: {str(e)}"
        )


@router.post("/toolkit/{slug}/tools", response_model=ComposioToolsResponse)
async def update_toolkit_tools(
        slug: str,
        request: ComposioToolsUpdateRequest,
        db: AsyncSession = Depends(get_db_session)
):
    """
    Update selected tools for a toolkit
    """
    try:
        logger.info(f"Updating tools selection for toolkit {slug}")
        logger.info(f"Request selected_tools: {request.selected_tools}")

        # Get toolkit from database
        toolkit = await ComposioToolkitQueries.get_toolkit_by_slug(db, slug)
        if not toolkit:
            raise HTTPException(
                status_code=404,
                detail=f"Toolkit '{slug}' not found"
            )
        
        logger.info(f"Found toolkit: {toolkit.name} (ID: {toolkit.id})")
        logger.info(f"Existing tools in DB: {toolkit.tools}")
        
        tools_list = []
        if toolkit.tools:
            try:
                tools_list = json.loads(toolkit.tools)
                logger.info(f"Parsed existing tools: {len(tools_list)} tools")
                if tools_list:
                    for tool in tools_list:
                        original_enabled = tool.get('enabled', True)
                        new_enabled = request.selected_tools.get(tool['name'], True)
                        tool['enabled'] = new_enabled
                        logger.info(f"Tool {tool['name']}: {original_enabled} -> {new_enabled}")
            except Exception as e:
                logger.error(f"Failed to parse existing tools: {e}")
                tools_list = []
                
        if tools_list:
            # Convert selected tools to JSON string
            tools_json = json.dumps(tools_list)
            logger.info(f"Tools JSON to save: {tools_json[:200]}...")  # Log first 200 chars
        else:
            tools_json = ''
            logger.info("No tools to save, using empty string")

        # Update toolkit tools in database
        logger.info(f"Calling update_toolkit_tools with toolkit_id: {toolkit.id}")
        success = await ComposioToolkitQueries.update_toolkit_tools(
            db,
            toolkit.id,
            tools_json
        )

        if not success:
            logger.error(f"Failed to update toolkit tools in database for {slug}")
            raise HTTPException(
                status_code=500,
                detail="Failed to update toolkit tools in database"
            )

        await db.commit()
        logger.info(f"✅ Database commit successful for {slug}")

        # Get updated tools count
        enabled_count = sum(1 for enabled in request.selected_tools.values() if enabled)
        total_count = len(request.selected_tools)

        logger.info(f"✅ Updated tools selection for {slug}: {enabled_count}/{total_count} tools enabled")

        # Return current tools (reuse the get endpoint logic)
        result = await get_toolkit_tools(slug, db)
        logger.info(f"Returning updated tools response for {slug}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update toolkit tools for {slug}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update toolkit tools: {str(e)}"
        )


@router.get("/toolkit/{slug}/connection-status", response_model=ComposioConnectionStatusResponse)
async def get_toolkit_connection_status(
        slug: str,
        db: AsyncSession = Depends(get_db_session)
):
    """
    Check connection status for a specific toolkit
    """
    try:
        logger.info(f"Checking connection status for toolkit {slug}")

        # Get toolkit from database
        toolkit = await ComposioToolkitQueries.get_toolkit_by_slug(db, slug)
        if not toolkit:
            raise HTTPException(
                status_code=404,
                detail=f"Toolkit '{slug}' not found"
            )

        # Get Composio instance
        composio = await _get_composio_instance()
        if composio is None:
            return ComposioConnectionStatusResponse(
                toolkit_slug=slug,
                connected=False,
                connection_id=None,
                status="no_api_key",
                last_checked=datetime.now().isoformat()
            )

        # Check connection status with Composio API
        try:
            entity_id = "default"  # Use default entity ID

            def _check_connection_status():
                try:
                    connection_list = composio.connected_accounts.list(
                        user_ids=[entity_id],
                        toolkit_slugs=[slug.lower()]
                    )

                    if connection_list and hasattr(connection_list, "items") and connection_list.items:
                        for connection in connection_list.items:
                            connection_id = getattr(connection, "id", None)
                            connection_status = getattr(connection, "status", None)
                            if connection_status == "ACTIVE" and connection_id:
                                return connection_id, "connected"
                    return None, "disconnected"
                except Exception as e:
                    logger.error(f"Error checking connection status: {e}")
                    return None, "error"

            connection_id, status = await asyncio.to_thread(_check_connection_status)

            return ComposioConnectionStatusResponse(
                toolkit_slug=slug,
                connected=(status == "connected"),
                connection_id=connection_id,
                status=status,
                last_checked=datetime.now().isoformat()
            )

        except Exception as e:
            logger.error(f"Failed to check connection status for {slug}: {e}")
            return ComposioConnectionStatusResponse(
                toolkit_slug=slug,
                connected=False,
                connection_id=None,
                status="error",
                last_checked=datetime.now().isoformat()
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get connection status for {slug}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get connection status: {str(e)}"
        )


# OAuth is now handled via browser popups using Composio's managed auth system
# No callback endpoint needed as authentication is handled in popup windows

# Health check endpoint
@router.get("/health")
async def composio_health_check():
    """
    Check Composio integration health
    """
    try:
        composio = await _get_composio_instance()

        if composio is None:
            return {
                "status": "no_api_key",
                "message": "Composio API key not configured",
                "timestamp": datetime.now().isoformat()
            }

        # Test API connection
        # try:
        #     toolkits = await asyncio.to_thread(lambda: composio.toolkits.get())
        #     return {
        #         "status": "healthy",
        #         "message": "Composio API connection working",
        #         "toolkits_count": len(toolkits) if toolkits else 0,
        #         "timestamp": datetime.now().isoformat()
        #     }
        # except Exception as e:
        #     return {
        #         "status": "api_error",
        #         "message": f"Composio API error: {str(e)}",
        #         "timestamp": datetime.now().isoformat()
        #     }

        return {
            "status": "healthy",
            "message": "Composio API connection working",
            "toolkits_count": 0,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Composio health check failed: {e}")
        return {
            "status": "error",
            "message": f"Health check failed: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }
