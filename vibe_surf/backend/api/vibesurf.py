"""
VibeSurf API Key Management
Handles VibeSurf API key validation and storage
"""

import uuid
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.manager import get_db_session
from ..database.queries import CredentialQueries
from vibe_surf.logger import get_logger

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