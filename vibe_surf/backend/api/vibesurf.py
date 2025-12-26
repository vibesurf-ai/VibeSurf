"""
VibeSurf API Key Management
Handles VibeSurf API key validation and storage
"""
import copy
import os
import uuid
import json
import re
import httpx
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ..database.manager import get_db_session
from ..database.queries import CredentialQueries
from vibe_surf.logger import get_logger
from vibe_surf.tools.website_api.newsnow.client import NewsNowClient
from vibe_surf.langflow.services.deps import session_scope, get_settings_service
from vibe_surf.langflow.services.auth.utils import create_super_user
from vibe_surf.langflow.api.v1.flows import _read_flow, _new_flow
from vibe_surf.langflow.services.database.models.folder.model import Folder
from vibe_surf.langflow.services.database.models.flow.model import FlowCreate

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/vibesurf", tags=["vibesurf"])

# Request/Response models
class VibeSurfApiKeyRequest(BaseModel):
    api_key: str

class VibeSurfApiKeyResponse(BaseModel):
    valid: bool
    message: str
    has_key: bool = False

class VibeSurfStatusResponse(BaseModel):
    connected: bool
    key_valid: bool
    has_key: bool
    message: str

class UUIDResponse(BaseModel):
    uuid: str

class VersionResponse(BaseModel):
    version: str

class ExtensionPathResponse(BaseModel):
    extension_path: str

class ImportWorkflowRequest(BaseModel):
    workflow_json: str

class ImportWorkflowResponse(BaseModel):
    success: bool
    message: str
    workflow_id: Optional[str] = None
    edit_url: Optional[str] = None

class ExportWorkflowResponse(BaseModel):
    success: bool
    message: str
    file_path: Optional[str] = None

class LocationLanguageResponse(BaseModel):
    country: str
    suggested_language: str
    detected_from_ip: bool = True

class SaveWorkflowRecordingRequest(BaseModel):
    name: str
    description: Optional[str] = None
    workflows: List[Dict[str, Any]]

class SaveWorkflowRecordingResponse(BaseModel):
    success: bool
    message: str
    file_path: Optional[str] = None
    langflow_path: Optional[str] = None
    workflow_id: Optional[str] = None

# Constants
VIBESURF_API_KEY_NAME = "VIBESURF_API_KEY"

def validate_vibesurf_api_key(api_key: str) -> bool:
    if not api_key or not isinstance(api_key, str):
        return False
    
    # Must start with 'vs-'
    if not api_key.startswith('vs-'):
        return False
    
    return len(api_key) == 51

@router.post("/verify-key", response_model=VibeSurfApiKeyResponse)
async def verify_vibesurf_key(
    request: VibeSurfApiKeyRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Verify and store VibeSurf API key"""
    try:
        api_key = request.api_key.strip()
        
        # Validate the API key
        is_valid = validate_vibesurf_api_key(api_key)
        
        if not is_valid:
            return VibeSurfApiKeyResponse(
                valid=False,
                message="Invalid VibeSurf API key. Key must start with 'vs-' and match the expected format.",
                has_key=False
            )
        
        # Store the valid API key
        success = await CredentialQueries.store_credential(
            db=db,
            key_name=VIBESURF_API_KEY_NAME,
            value=api_key,
            description="VibeSurf API Key for workflows access"
        )
        
        if not success:
            logger.error(f"Failed to store VibeSurf API key")
            return VibeSurfApiKeyResponse(
                valid=False,
                message="Failed to store API key",
                has_key=False
            )
        
        await db.commit()
        
        logger.info("VibeSurf API key validated and stored successfully")
        return VibeSurfApiKeyResponse(
            valid=True,
            message="VibeSurf API key is valid and has been saved",
            has_key=True
        )
        
    except Exception as e:
        logger.error(f"Error verifying VibeSurf API key: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to verify API key")

@router.get("/status", response_model=VibeSurfStatusResponse)
async def get_vibesurf_status(db: AsyncSession = Depends(get_db_session)):
    """Get VibeSurf connection status"""
    try:
        # Check if API key exists and is valid
        stored_key = await CredentialQueries.get_credential(db, VIBESURF_API_KEY_NAME)
        
        has_key = stored_key is not None
        key_valid = False
        
        if has_key:
            key_valid = validate_vibesurf_api_key(stored_key)
        
        connected = has_key and key_valid
        
        if connected:
            message = "VibeSurf API key is configured and valid"
        elif has_key and not key_valid:
            message = "VibeSurf API key exists but is invalid"
        else:
            message = "No VibeSurf API key configured"
        
        return VibeSurfStatusResponse(
            connected=connected,
            key_valid=key_valid,
            has_key=has_key,
            message=message
        )
        
    except Exception as e:
        logger.error(f"Error getting VibeSurf status: {e}")
        return VibeSurfStatusResponse(
            connected=False,
            key_valid=False,
            has_key=False,
            message="Failed to check VibeSurf status"
        )

@router.delete("/key")
async def delete_vibesurf_key(db: AsyncSession = Depends(get_db_session)):
    """Delete stored VibeSurf API key"""
    try:
        success = await CredentialQueries.delete_credential(db, VIBESURF_API_KEY_NAME)
        
        if success:
            await db.commit()
            return {"message": "VibeSurf API key deleted successfully"}
        else:
            return {"message": "No VibeSurf API key found to delete"}
            
    except Exception as e:
        logger.error(f"Error deleting VibeSurf API key: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete API key")

@router.get("/validate")
async def validate_current_key(db: AsyncSession = Depends(get_db_session)):
    """Validate currently stored VibeSurf API key"""
    try:
        stored_key = await CredentialQueries.get_credential(db, VIBESURF_API_KEY_NAME)
        
        if not stored_key:
            return {"valid": False, "message": "No API key stored"}
        
        is_valid = validate_vibesurf_api_key(stored_key)
        
        return {
            "valid": is_valid,
            "message": "API key is valid" if is_valid else "Stored API key is invalid"
        }
        
    except Exception as e:
        logger.error(f"Error validating current VibeSurf API key: {e}")
        return {"valid": False, "message": "Failed to validate API key"}

@router.get("/generate-uuid", response_model=UUIDResponse)
async def generate_uuid_v4():
    """Generate a new UUID v4"""
    try:
        new_uuid = str(uuid.uuid4())
        logger.info(f"Generated UUID: {new_uuid}")
        return UUIDResponse(uuid=new_uuid)
    except Exception as e:
        logger.error(f"Error generating UUID: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate UUID")

@router.post("/import-workflow", response_model=ImportWorkflowResponse)
async def import_workflow(
    request: ImportWorkflowRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Import workflow from JSON string"""
    try:
        # Parse and validate JSON
        try:
            # In case user uses org langflow
            workflow_json = request.workflow_json
            workflow_json = workflow_json.replace("from langflow.", 'from vibe_surf.langflow.')
            workflow_json = workflow_json.replace("import langflow.", 'import vibe_surf.langflow.')
            workflow_data = json.loads(workflow_json)
        except json.JSONDecodeError as e:
            return ImportWorkflowResponse(
                success=False,
                message=f"Invalid JSON format: {str(e)}"
            )
        
        # Validate required fields
        required_fields = ["name", "description", "data"]
        missing_fields = [field for field in required_fields if field not in workflow_data]
        if missing_fields:
            return ImportWorkflowResponse(
                success=False,
                message=f"Missing required fields: {', '.join(missing_fields)}"
            )
        
        # Validate data structure
        if not isinstance(workflow_data.get("data"), dict):
            return ImportWorkflowResponse(
                success=False,
                message="'data' field must be an object"
            )
        
        data = workflow_data["data"]
        if "nodes" not in data or "edges" not in data:
            return ImportWorkflowResponse(
                success=False,
                message="'data' must contain 'nodes' and 'edges' fields"
            )
        
        # Get VibeSurf API key
        api_key = await CredentialQueries.get_credential(db, VIBESURF_API_KEY_NAME)
        if not api_key or not validate_vibesurf_api_key(api_key):
            return ImportWorkflowResponse(
                success=False,
                message="Valid VibeSurf API key required"
            )
        
        # Get settings for authentication
        settings_service = get_settings_service()
        username = settings_service.auth_settings.SUPERUSER
        password = settings_service.auth_settings.SUPERUSER_PASSWORD
        
        # Use direct database calls instead of HTTP
        try:
            async with session_scope() as langflow_session:
                current_user = await create_super_user(db=langflow_session, username=username, password=password)
                
                # Get projects to obtain folder_id
                projects = (
                    await langflow_session.exec(
                        select(Folder).where(Folder.user_id == current_user.id)
                    )
                ).all()
                
                # Use the first project's ID as folder_id
                if projects and len(projects) > 0:
                    folder_id = projects[0].id
                else:
                    # Create a default folder if none exists
                    from vibe_surf.langflow.services.database.models.folder.model import FolderCreate
                    default_folder = Folder.model_validate(
                        FolderCreate(name="My Projects", description="Default folder"),
                        from_attributes=True
                    )
                    default_folder.user_id = current_user.id
                    langflow_session.add(default_folder)
                    await langflow_session.commit()
                    await langflow_session.refresh(default_folder)
                    folder_id = default_folder.id

                # Prepare flow data
                flow_data = FlowCreate(
                    name=workflow_data["name"],
                    description=workflow_data.get("description", ""),
                    data=workflow_data["data"],
                    folder_id=folder_id,
                    user_id=current_user.id
                )
                
                # Create workflow using direct function call
                db_flow = await _new_flow(
                    session=langflow_session,
                    flow=flow_data,
                    user_id=current_user.id
                )
                
                await langflow_session.commit()
                await langflow_session.refresh(db_flow)
                
                workflow_id = str(db_flow.id)
                backend_port = os.getenv("VIBESURF_BACKEND_PORT", "9335")
                edit_url = f"http://localhost:{backend_port}/flow/{workflow_id}"
                
                logger.info(f"Successfully imported workflow: {workflow_id}")
                return ImportWorkflowResponse(
                    success=True,
                    message="Workflow imported successfully",
                    workflow_id=workflow_id,
                    edit_url=edit_url
                )
                
        except Exception as e:
            logger.error(f"Error during workflow creation: {e}")
            import traceback
            traceback.print_exc()
            return ImportWorkflowResponse(
                success=False,
                message=f"Failed to create workflow: {str(e)}"
            )
            
    except Exception as e:
        logger.error(f"Error importing workflow: {e}")
        import traceback
        traceback.print_exc()
        return ImportWorkflowResponse(
            success=False,
            message="Failed to import workflow"
        )

@router.get("/export-workflow/{flow_id}", response_model=ExportWorkflowResponse)
async def export_workflow(
    flow_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Export workflow to JSON file"""
    try:
        # Get VibeSurf API key
        api_key = await CredentialQueries.get_credential(db, VIBESURF_API_KEY_NAME)
        if not api_key or not validate_vibesurf_api_key(api_key):
            return ExportWorkflowResponse(
                success=False,
                message="Valid VibeSurf API key required"
            )
        
        # Get settings for authentication
        settings_service = get_settings_service()
        username = settings_service.auth_settings.SUPERUSER
        password = settings_service.auth_settings.SUPERUSER_PASSWORD
        
        try:
            # Convert flow_id to UUID
            from uuid import UUID
            try:
                flow_uuid = UUID(flow_id)
            except ValueError:
                return ExportWorkflowResponse(
                    success=False,
                    message="Invalid flow ID format"
                )
            
            # Use direct database calls instead of HTTP
            async with session_scope() as langflow_session:
                current_user = await create_super_user(db=langflow_session, username=username, password=password)
                
                # Fetch workflow from database
                db_flow = await _read_flow(session=langflow_session, flow_id=flow_uuid, user_id=current_user.id)
                
                if not db_flow:
                    return ExportWorkflowResponse(
                        success=False,
                        message=f"Workflow not found: {flow_id}"
                    )
                
                # Convert to dict and prepare for export
                workflow_data = {
                    "name": db_flow.name,
                    "description": db_flow.description,
                    "data": db_flow.data
                }
                
                # Remove API keys (password fields) to match frontend behavior
                if "data" in workflow_data and "nodes" in workflow_data["data"]:
                    try:
                        for node in workflow_data["data"]["nodes"]:
                            if node.get("type") == "genericNode":
                                template = node.get("data", {}).get("node", {}).get("template", {})
                                for key, field in template.items():
                                    if isinstance(field, dict) and field.get("password") is True:
                                        field["value"] = ""
                    except Exception as e:
                        logger.warning(f"Error filtering API keys during export: {e}")

                # Get workflow name
                flow_name = workflow_data.get("name", "workflow")
                # Sanitize filename by removing invalid characters
                safe_flow_name = "".join(c for c in flow_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                safe_flow_name = safe_flow_name.replace(' ', '_')

                flow_id_short = flow_id[:4]
                filename = f"{safe_flow_name}-{flow_id_short}.json"
                
                # Get VibeSurf work directory and create workflows subdirectory
                from vibe_surf import common
                work_dir = common.get_workspace_dir()
                workflows_dir = Path(work_dir) / "workflows" / "exported_json"
                workflows_dir.mkdir(parents=True, exist_ok=True)
                
                # Full file path
                file_path = workflows_dir / filename
                
                # Save workflow JSON to file
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(workflow_data, f, indent=2, ensure_ascii=False)
                
                logger.info(f"Successfully exported workflow {flow_id} to {file_path}")
                return ExportWorkflowResponse(
                    success=True,
                    message="Workflow exported successfully",
                    file_path=str(file_path)
                )
                
        except Exception as e:
            logger.error(f"Error during workflow export: {e}")
            import traceback
            traceback.print_exc()
            return ExportWorkflowResponse(
                success=False,
                message=f"Failed to export workflow: {str(e)}"
            )
            
    except Exception as e:
        logger.error(f"Error exporting workflow: {e}")
        import traceback
        traceback.print_exc()
        return ExportWorkflowResponse(
            success=False,
            message="Failed to export workflow"
        )

@router.get("/version", response_model=VersionResponse)
async def get_vibesurf_version():
    """Get VibeSurf package version"""
    try:
        import vibe_surf
        version = vibe_surf.__version__
        logger.info(f"VibeSurf version: {version}")
        return VersionResponse(version=version)
    except Exception as e:
        logger.error(f"Error getting VibeSurf version: {e}")
        raise HTTPException(status_code=500, detail="Failed to get version")

@router.post("/workflows/save-recording", response_model=SaveWorkflowRecordingResponse)
async def save_workflow_recording(request: SaveWorkflowRecordingRequest):
    """Save workflow recording to workdir/workflows/raws/ directory and convert to Langflow format"""
    try:
        # Get workspace directory
        from vibe_surf import common
        work_dir = common.get_workspace_dir()
        
        # Create workflows/raws directory if it doesn't exist
        workflows_dir = Path(work_dir) / "workflows" / "raws"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Sanitize filename by removing invalid characters
        sanitized_name = "".join(c for c in request.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        sanitized_name = sanitized_name.replace(' ', '_')
        
        # Create filename
        filename = f"{timestamp}_{sanitized_name}.json"
        file_path = workflows_dir / filename
        
        # Prepare workflow data with metadata
        workflow_data = {
            "name": request.name,
            "description": request.description or "",
            "workflows": request.workflows,
            "timestamp": datetime.now().isoformat(),
            "version": "1.0"
        }
        
        # Save raw workflow to file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(workflow_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Successfully saved workflow recording to {file_path}")
        
        # Convert to Langflow format and save to database
        langflow_path = None
        workflow_id = None
        conversion_error = None
        
        try:
            from vibe_surf.backend.utils.workflow_converter import convert_and_save_workflow
            
            conversion_result = await convert_and_save_workflow(
                raw_json_path=str(file_path),
                output_json_path=None,
                save_to_db=True
            )
            
            if conversion_result["success"]:
                langflow_path = conversion_result["output_path"]
                db_flow = conversion_result["db_flow"]
                if db_flow:
                    workflow_id = str(db_flow.id)
                    logger.info(f"Workflow converted and saved to database with ID: {workflow_id}")
                else:
                    logger.warning("Workflow converted but not saved to database")
            else:
                conversion_error = conversion_result['message']
                logger.error(f"Failed to convert workflow: {conversion_error}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to convert workflow: {conversion_error}"
                )
                
        except HTTPException:
            # Re-raise HTTPException
            raise
        except Exception as conv_error:
            logger.error(f"Error during workflow conversion: {conv_error}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Error during workflow conversion: {str(conv_error)}"
            )
        
        return SaveWorkflowRecordingResponse(
            success=True,
            message="Workflow recording saved and converted successfully",
            file_path=str(file_path),
            langflow_path=langflow_path,
            workflow_id=workflow_id
        )
        
    except Exception as e:
        logger.error(f"Error saving workflow recording: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save workflow recording: {str(e)}")

async def get_extension_path():
    """Get Chrome extension directory path"""
    try:
        import vibe_surf
        vibe_surf_dir = os.path.dirname(vibe_surf.__file__)
        extension_path = os.path.join(vibe_surf_dir, 'chrome_extension')
        logger.info(f"Chrome extension path: {extension_path}")
        return ExtensionPathResponse(extension_path=extension_path)
    except Exception as e:
        logger.error(f"Error getting extension path: {e}")
        raise HTTPException(status_code=500, detail="Failed to get extension path")

@router.get("/serve")
async def serve_file(path: str):
    """Serve a local file securely"""
    try:
        # Decode path if it's URL encoded? FastAPI handles query params
        # Check if path is relative
        file_path = Path(path)
        
        # If relative, make it relative to workspace root
        if not file_path.is_absolute():
            from vibe_surf import common
            workspace_dir = common.get_workspace_dir()
            file_path = Path(workspace_dir) / path
            
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
            
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="Not a file")
            
        return FileResponse(str(file_path))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving file {path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to serve file: {str(e)}")


# News API endpoints
class NewsSourcesResponse(BaseModel):
    sources: Dict[str, Dict[str, Any]]

class NewsResponse(BaseModel):
    news: Dict[str, List[Dict[str, Any]]]
    sources_metadata: Dict[str, Dict[str, Any]]

class WeatherResponse(BaseModel):
    location: str
    temp_c: str
    condition: str
    wind_speed: str
    details: Dict[str, Any]

class IPLocationData(BaseModel):
    """IP location data returned by ipinfo.io"""
    city: str = ""
    country: str = ""
    loc: str = ""  # Format: "latitude,longitude"
    latitude: float = None
    longitude: float = None
    detected: bool = False

async def get_ip_location() -> IPLocationData:
    """
    Get IP location information using ipinfo.io

    Returns:
        IPLocationData with city, country, and coordinates
        If detection fails, returns empty location with detected=False

    Example:
        location = await get_ip_location()
        if location.detected:
            print(f"City: {location.city}, Country: {location.country}")
    """
    result = IPLocationData()

    try:
        # trust_env=False prevents httpx from using system proxy settings
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.get("http://ipinfo.io/json", timeout=2.0)
            if response.status_code == 200:
                ip_data = response.json()
                result.city = ip_data.get("city", "")
                result.country = ip_data.get("country", "")
                result.loc = ip_data.get("loc", "")

                # Parse coordinates
                if result.loc and "," in result.loc:
                    lat_str, lon_str = result.loc.split(",")
                    try:
                        result.latitude = float(lat_str.strip())
                        result.longitude = float(lon_str.strip())
                    except ValueError:
                        logger.warning(f"Invalid coordinates format: {result.loc}")

                result.detected = bool(result.country)
                logger.debug(f"IP location detected: city={result.city}, country={result.country}")

    except (httpx.TimeoutException, httpx.RequestError, ValueError) as e:
        logger.warning(f"Error getting IP location (using defaults): {e}")
    except Exception as e:
        logger.warning(f"Unexpected error getting IP location (using defaults): {e}")

    return result

@router.get("/weather", response_model=WeatherResponse)
async def get_weather():
    """Get weather information based on IP location using open-meteo.com"""
    try:
        # Default to San Francisco coordinates if geolocation fails
        latitude = 37.7749
        longitude = -122.4194
        display_location = "San Francisco, US"

        # Get location from IP using shared function
        ip_location = await get_ip_location()

        if ip_location.detected:
            # Use detected location
            if ip_location.latitude is not None and ip_location.longitude is not None:
                latitude = ip_location.latitude
                longitude = ip_location.longitude

            if ip_location.city and ip_location.country:
                display_location = f"{ip_location.city}, {ip_location.country}"
            elif ip_location.country:
                display_location = ip_location.country

            logger.debug(f"Location detected: {display_location} ({latitude}, {longitude})")
        
        # Get weather from open-meteo.com
        weather_url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current_weather": "true"
        }
        
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.get(weather_url, params=params, timeout=3.0)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch weather data")
            weather_data = response.json()
        
        # Extract current weather data
        current = weather_data.get("current_weather", {})
        temp_c = current.get("temperature", 0)
        wind_speed = current.get("windspeed", 0)
        weather_code = current.get("weathercode", 0)
        
        # Map WMO weather codes to descriptions
        # https://open-meteo.com/en/docs
        weather_code_map = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Foggy",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            71: "Slight snow",
            73: "Moderate snow",
            75: "Heavy snow",
            77: "Snow grains",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            85: "Slight snow showers",
            86: "Heavy snow showers",
            95: "Thunderstorm",
            96: "Thunderstorm with slight hail",
            99: "Thunderstorm with heavy hail"
        }
        
        condition = weather_code_map.get(weather_code, "Unknown")
        
        return WeatherResponse(
            location=display_location,
            temp_c=str(int(temp_c)),
            condition=condition,
            wind_speed=str(int(wind_speed)),
            details={
                "temperature": temp_c,
                "windspeed": wind_speed,
                "weathercode": weather_code,
                "time": current.get("time", ""),
                "winddirection": current.get("winddirection", 0)
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting weather: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get weather: {str(e)}")

@router.get("/news/sources", response_model=NewsSourcesResponse)
async def get_news_sources(news_type: Optional[str] = None):
    """Get available news sources with metadata
    
    Args:
        news_type: Optional filter by news type ("realtime", "hottest", or None for all)
    """
    try:
        client = NewsNowClient()
        sources = client.get_available_sources(news_type=news_type)
        return NewsSourcesResponse(sources=sources)
    except Exception as e:
        logger.error(f"Error getting news sources: {e}")
        raise HTTPException(status_code=500, detail="Failed to get news sources")

@router.get("/news", response_model=NewsResponse)
async def get_news(
    source_id: Optional[str] = None,
    news_type: Optional[str] = None,
    count: int = 10
):
    """Get news from sources

    Args:
        source_id: Optional source ID. If None, fetches from all sources based on news_type
        news_type: Optional news type filter ("realtime", "hottest", or None for both)
        count: Maximum number of news items to return per source (default: 10)
    """
    try:
        client = NewsNowClient()

        # Client handles all filtering logic internally
        news_data = await client.get_news(
            source_id=source_id,
            news_type=news_type,
            count=count
        )

        # Get metadata for the sources that have news
        sources_metadata = {}
        for sid in news_data.keys():
            if sid in client.sources:
                metadata = client.sources[sid]
                sources_metadata[sid] = {
                    "name": metadata.get("name", ""),
                    "home": metadata.get("home", ""),
                    "color": metadata.get("color", ""),
                    "title": metadata.get("title", ""),
                    "type": metadata.get("type", "all")
                }

        return NewsResponse(
            news=news_data,
            sources_metadata=sources_metadata
        )
    except Exception as e:
        logger.error(f"Error getting news: {e}")
        raise HTTPException(status_code=500, detail="Failed to get news")

@router.get("/location-language", response_model=LocationLanguageResponse)
async def get_location_language():
    """Get suggested language based on user's IP location.

    Returns:
        - China (CN): zh_CN
        - All other countries: en (English)
    """
    try:
        # Default to English if detection fails
        country = "US"
        suggested_language = "en"

        # Get location from IP using shared function
        ip_location = await get_ip_location()

        if ip_location.detected:
            country = ip_location.country
            if country == "CN":
                suggested_language = "zh_CN"
            else:
                suggested_language = "en"

            logger.info(f"Location language detection: country={country}, suggested_language={suggested_language}")

        return LocationLanguageResponse(
            country=country,
            suggested_language=suggested_language,
            detected_from_ip=ip_location.detected
        )

    except Exception as e:
        logger.error(f"Error getting location language: {e}")
        # Return default English on any error
        return LocationLanguageResponse(
            country="US",
            suggested_language="en",
            detected_from_ip=False
        )