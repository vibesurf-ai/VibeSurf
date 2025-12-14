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

from ..database.manager import get_db_session
from ..database.queries import CredentialQueries
from vibe_surf.logger import get_logger
from vibe_surf.tools.website_api.newsnow.client import NewsNowClient

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

        # for edge in data["edges"]:
        #     if "sourceHandle" in edge:
        #         edge_before = edge["sourceHandle"]
        #         edge["sourceHandle"] = re.sub(r'\s+', '', edge_before).strip()
        #         edge_after = edge["sourceHandle"]
        #         print(f"{edge_before} -> {edge_after}")
        #
        #     if "targetHandle" in edge:
        #         edge_before = edge["targetHandle"]
        #         edge["targetHandle"] = re.sub(r'\s+', '', edge_before).strip()
        #         edge_after = edge["targetHandle"]
        #         print(f"{edge_before} -> {edge_after}")
        
        # Get VibeSurf API key
        api_key = await CredentialQueries.get_credential(db, VIBESURF_API_KEY_NAME)
        if not api_key or not validate_vibesurf_api_key(api_key):
            return ImportWorkflowResponse(
                success=False,
                message="Valid VibeSurf API key required"
            )
        
        # Get backend base URL (assuming local langflow instance)
        backend_port = os.getenv("VIBESURF_BACKEND_PORT", "9335")
        backend_base_url = f'http://localhost:{backend_port}'
        
        # Get projects to obtain folder_id
        try:
            async with httpx.AsyncClient() as client:
                projects_response = await client.get(
                    f"{backend_base_url}/api/v1/projects/",
                    timeout=30.0
                )
                
                if projects_response.status_code != 200:
                    return ImportWorkflowResponse(
                        success=False,
                        message="Failed to fetch projects"
                    )
                
                projects = projects_response.json()
                
                # Use the first project's ID as folder_id
                if isinstance(projects, list) and len(projects) > 0:
                    folder_id = projects[0].get("id")
                else:
                    folder_id = ""

                import_data = copy.deepcopy(workflow_data)
                import_data["folder_id"] = folder_id

                if "user_id" in import_data:
                    del import_data["user_id"]
                
                # Create workflow
                create_response = await client.post(
                    f"{backend_base_url}/api/v1/flows/",
                    json=import_data,
                    timeout=30.0
                )
                
                if create_response.status_code not in [200, 201]:
                    error_detail = create_response.text
                    return ImportWorkflowResponse(
                        success=False,
                        message=f"Failed to create workflow: {error_detail}"
                    )
                
                created_workflow = create_response.json()
                workflow_id = created_workflow.get("id")
                edit_url = f"{backend_base_url}/flow/{workflow_id}"
                
                logger.info(f"Successfully imported workflow: {workflow_id}")
                return ImportWorkflowResponse(
                    success=True,
                    message="Workflow imported successfully",
                    workflow_id=workflow_id,
                    edit_url=edit_url
                )
                
        except httpx.RequestError as e:
            logger.error(f"HTTP request failed during workflow import: {e}")
            return ImportWorkflowResponse(
                success=False,
                message="Failed to communicate with workflow service"
            )
        except Exception as e:
            logger.error(f"Error during workflow creation: {e}")
            return ImportWorkflowResponse(
                success=False,
                message=f"Failed to create workflow: {str(e)}"
            )
            
    except Exception as e:
        logger.error(f"Error importing workflow: {e}")
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
        
        # Get backend base URL (assuming local langflow instance)
        backend_port = os.getenv("VIBESURF_BACKEND_PORT", "9335")
        backend_base_url = f'http://localhost:{backend_port}'
        
        try:
            async with httpx.AsyncClient() as client:
                # Fetch workflow data
                workflow_response = await client.get(
                    f"{backend_base_url}/api/v1/flows/{flow_id}",
                    headers={"accept": "application/json"},
                    timeout=30.0
                )
                
                if workflow_response.status_code != 200:
                    return ExportWorkflowResponse(
                        success=False,
                        message=f"Failed to fetch workflow: {workflow_response.status_code}"
                    )
                
                workflow_data = workflow_response.json()
                if "user_id" in workflow_data:
                    del workflow_data["user_id"]
                if "folder_id" in workflow_data:
                    del workflow_data["folder_id"]
                
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

                # Get workflow name from the response
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
                
        except httpx.RequestError as e:
            logger.error(f"HTTP request failed during workflow export: {e}")
            return ExportWorkflowResponse(
                success=False,
                message="Failed to communicate with workflow service"
            )
        except Exception as e:
            logger.error(f"Error during workflow export: {e}")
            return ExportWorkflowResponse(
                success=False,
                message=f"Failed to export workflow: {str(e)}"
            )
            
    except Exception as e:
        logger.error(f"Error exporting workflow: {e}")
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

@router.get("/weather", response_model=WeatherResponse)
async def get_weather():
    """Get weather information based on IP location using open-meteo.com"""
    try:
        # Default to San Francisco coordinates if geolocation fails
        latitude = 37.7749
        longitude = -122.4194
        display_location = "San Francisco, US"
        
        # Get location from IP using ipinfo.io (disable proxy to get real IP)
        try:
            # trust_env=False prevents httpx from using system proxy settings
            async with httpx.AsyncClient(trust_env=False) as client:
                response = await client.get("http://ipinfo.io/json", timeout=2.0)
                if response.status_code == 200:
                    ip_data = response.json()
                    city = ip_data.get("city", "")
                    country = ip_data.get("country", "")
                    loc = ip_data.get("loc", "")
                    
                    if loc and "," in loc:
                        # loc format is "latitude,longitude"
                        lat_str, lon_str = loc.split(",")
                        latitude = float(lat_str.strip())
                        longitude = float(lon_str.strip())
                        
                        if city and country:
                            display_location = f"{city}, {country}"
                        elif country:
                            display_location = country
                        
                        logger.debug(f"Location detected: {display_location} ({latitude}, {longitude})")
        except (httpx.TimeoutException, httpx.RequestError, ValueError) as e:
            logger.warning(f"Error getting IP location (using San Francisco as default): {e}")
        except Exception as e:
            logger.warning(f"Unexpected error getting IP location (using San Francisco as default): {e}")
        
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