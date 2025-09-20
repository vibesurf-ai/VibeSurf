"""
Tools API endpoints for VibeSurf Backend

Handles voice recognition and other tool-related operations.
"""
import pdb

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
import os
import logging
from datetime import datetime

from vibe_surf.tools.voice_asr import QwenASR, OpenAIASR, GeminiASR

from ..database.manager import get_db_session
from ..database.queries import VoiceProfileQueries
from ..voice_model_config import VOICE_MODELS


router = APIRouter(prefix="/voices", tags=["voices"])

from vibe_surf.logger import get_logger

logger = get_logger(__name__)


# Pydantic models for request validation
class VoiceProfileCreate(BaseModel):
    voice_profile_name: str
    voice_model_type: str  # "asr" or "tts"
    voice_model_name: str
    api_key: Optional[str] = None
    voice_meta_params: Optional[Dict[str, Any]] = None
    description: Optional[str] = None

class VoiceProfileUpdate(BaseModel):
    voice_model_type: Optional[str] = None
    voice_model_name: Optional[str] = None
    api_key: Optional[str] = None
    voice_meta_params: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


@router.post("/voice-profiles")
async def create_voice_profile(
    profile_data: VoiceProfileCreate,
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new voice profile"""
    try:
        # Validate voice_model_type
        if profile_data.voice_model_type not in ["asr", "tts"]:
            raise HTTPException(
                status_code=400,
                detail="voice_model_type must be 'asr' or 'tts'"
            )
        
        # Check if profile name already exists
        existing_profile = await VoiceProfileQueries.get_profile(db, profile_data.voice_profile_name)
        if existing_profile:
            raise HTTPException(
                status_code=400,
                detail=f"Voice profile '{profile_data.voice_profile_name}' already exists"
            )
        
        # Create the profile
        created_profile = await VoiceProfileQueries.create_profile(
            db=db,
            voice_profile_name=profile_data.voice_profile_name,
            voice_model_type=profile_data.voice_model_type,
            voice_model_name=profile_data.voice_model_name,
            api_key=profile_data.api_key,
            voice_meta_params=profile_data.voice_meta_params,
            description=profile_data.description
        )
        
        await db.commit()
        
        return {
            "success": True,
            "message": f"Voice profile '{profile_data.voice_profile_name}' created successfully",
            "profile": created_profile
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create voice profile: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create voice profile: {str(e)}"
        )


@router.put("/voice-profiles/{voice_profile_name}")
async def update_voice_profile(
    voice_profile_name: str,
    profile_data: VoiceProfileUpdate,
    db: AsyncSession = Depends(get_db_session)
):
    """Update an existing voice profile"""
    try:
        # Check if profile exists
        existing_profile = await VoiceProfileQueries.get_profile(db, voice_profile_name)
        if not existing_profile:
            raise HTTPException(
                status_code=404,
                detail=f"Voice profile '{voice_profile_name}' not found"
            )
        
        # Validate voice_model_type if provided
        if profile_data.voice_model_type and profile_data.voice_model_type not in ["asr", "tts"]:
            raise HTTPException(
                status_code=400,
                detail="voice_model_type must be 'asr' or 'tts'"
            )
        
        # Prepare update data (exclude None values)
        update_data = {}
        for field, value in profile_data.dict(exclude_unset=True).items():
            if value is not None:
                update_data[field] = value
        
        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="No valid fields provided for update"
            )
        
        # Update the profile
        success = await VoiceProfileQueries.update_profile(
            db=db,
            voice_profile_name=voice_profile_name,
            updates=update_data
        )
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to update voice profile"
            )
        
        await db.commit()
        
        # Get updated profile
        updated_profile = await VoiceProfileQueries.get_profile(db, voice_profile_name)
        
        return {
            "success": True,
            "message": f"Voice profile '{voice_profile_name}' updated successfully",
            "profile": {
                "profile_id": updated_profile.profile_id,
                "voice_profile_name": updated_profile.voice_profile_name,
                "voice_model_type": updated_profile.voice_model_type.value,
                "voice_model_name": updated_profile.voice_model_name,
                "voice_meta_params": updated_profile.voice_meta_params,
                "description": updated_profile.description,
                "is_active": updated_profile.is_active,
                "created_at": updated_profile.created_at,
                "updated_at": updated_profile.updated_at,
                "last_used_at": updated_profile.last_used_at
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update voice profile: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update voice profile: {str(e)}"
        )


@router.delete("/voice-profiles/{voice_profile_name}")
async def delete_voice_profile(
    voice_profile_name: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Delete a voice profile"""
    try:
        # Check if profile exists
        existing_profile = await VoiceProfileQueries.get_profile(db, voice_profile_name)
        if not existing_profile:
            raise HTTPException(
                status_code=404,
                detail=f"Voice profile '{voice_profile_name}' not found"
            )
        
        # Delete the profile
        success = await VoiceProfileQueries.delete_profile(db, voice_profile_name)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete voice profile"
            )
        
        await db.commit()
        
        return {
            "success": True,
            "message": f"Voice profile '{voice_profile_name}' deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete voice profile: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete voice profile: {str(e)}"
        )


@router.post("/asr")
async def voice_recognition(
    audio_file: UploadFile = File(...),
    voice_profile_name: str = None,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Voice recognition using specified voice profile
    
    Args:
        audio_file: Audio file to transcribe
        voice_profile_name: Name of the voice profile to use (required)
        db: Database session
    
    Returns:
        Dict with recognized text
    """
    from .. import shared_state
    try:
        # Validate required parameters
        if not voice_profile_name:
            raise HTTPException(
                status_code=400,
                detail="voice_profile_name parameter is required"
            )
        
        if not audio_file or not audio_file.filename:
            raise HTTPException(
                status_code=400,
                detail="audio_file is required and must have a filename"
            )
        
        # Log the incoming request for debugging
        logger.info(f"ASR request: voice_profile_name='{voice_profile_name}', audio_file='{audio_file.filename}', size={audio_file.size if hasattr(audio_file, 'size') else 'unknown'}")
        
        # Get voice profile with decrypted API key
        profile_data = await VoiceProfileQueries.get_profile_with_decrypted_key(db, voice_profile_name)
        if not profile_data:
            raise HTTPException(
                status_code=404,
                detail=f"Voice profile '{voice_profile_name}' not found"
            )
        
        # Check if profile is active
        if not profile_data.get("is_active"):
            raise HTTPException(
                status_code=400,
                detail=f"Voice profile '{voice_profile_name}' is inactive"
            )
        
        # Check if profile is for ASR
        if profile_data.get("voice_model_type") != "asr":
            raise HTTPException(
                status_code=400,
                detail=f"Voice profile '{voice_profile_name}' is not an ASR profile"
            )
        
        # Get model configuration
        voice_model_name = profile_data.get("voice_model_name")
        model_config = VOICE_MODELS.get(voice_model_name)
        if not model_config:
            raise HTTPException(
                status_code=400,
                detail=f"Voice model '{voice_model_name}' is not supported"
            )
        
        # Save uploaded file permanently in workspace_dir/audios/
        saved_file_path = None
        try:
            # Get workspace directory
            workspace_dir = shared_state.workspace_dir
            if not workspace_dir:
                raise HTTPException(
                    status_code=500,
                    detail="Workspace directory not configured"
                )
            
            # Create audios directory if it doesn't exist
            audios_dir = os.path.join(workspace_dir, "audios")
            os.makedirs(audios_dir, exist_ok=True)
            
            # Generate timestamp-based filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # microseconds to milliseconds
            file_extension = ".wav"  # Default to wav
            if audio_file.filename:
                original_ext = os.path.splitext(audio_file.filename)[1]
                if original_ext:
                    file_extension = original_ext
            
            saved_filename = f"asr-{timestamp}{file_extension}"
            saved_file_path = os.path.join(audios_dir, saved_filename)
            
            # Save the audio file
            content = await audio_file.read()
            with open(saved_file_path, "wb") as f:
                f.write(content)
            
            # Initialize ASR
            api_key = profile_data.get("api_key")
            voice_meta_params = profile_data.get("voice_meta_params", {})
            asr_model_name = voice_meta_params.get("asr_model_name", "")
            recognized_text = ""
            if voice_model_name == "qwen-asr":
                asr = QwenASR(model=asr_model_name, api_key=api_key)
                recognized_text = asr.asr(wav_url=saved_file_path)
            elif voice_model_name == "openai-asr":
                # Support custom base_url for OpenAI
                base_url = voice_meta_params.get("base_url")
                asr = OpenAIASR(model=asr_model_name, api_key=api_key, base_url=base_url)
                recognized_text = asr.asr(wav_url=saved_file_path)
            elif voice_model_name == "gemini-asr":
                asr = GeminiASR(model=asr_model_name, api_key=api_key)
                recognized_text = asr.asr(wav_url=saved_file_path)
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Voice model '{voice_model_name}' is not supported"
                )
            logger.debug(f"Recognized text: {recognized_text}")
            # Update last used timestamp
            await VoiceProfileQueries.update_last_used(db, voice_profile_name)
            await db.commit()
            
            return {
                "success": True,
                "voice_profile_name": voice_profile_name,
                "voice_model_name": voice_model_name,
                "recognized_text": recognized_text,
                "filename": audio_file.filename,
                "saved_audio_path": saved_file_path
            }
            
        except Exception as e:
            # If there's an error, we might want to clean up the saved file
            if saved_file_path and os.path.exists(saved_file_path):
                try:
                    os.unlink(saved_file_path)
                except:
                    pass  # Ignore cleanup errors
            raise e
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to perform voice recognition: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Voice recognition failed: {str(e)}"
        )


@router.get("/voice-profiles")
async def list_voice_profiles(
    voice_model_type: Optional[str] = None,
    active_only: bool = True,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_session)
):
    """List voice profiles"""
    try:
        profiles = await VoiceProfileQueries.list_profiles(
            db=db,
            voice_model_type=voice_model_type,
            active_only=active_only,
            limit=limit,
            offset=offset
        )
        
        profile_list = []
        for profile in profiles:
            profile_data = {
                "profile_id": profile.profile_id,
                "voice_profile_name": profile.voice_profile_name,
                "voice_model_type": profile.voice_model_type.value,
                "voice_model_name": profile.voice_model_name,
                "voice_meta_params": profile.voice_meta_params,
                "description": profile.description,
                "is_active": profile.is_active,
                "created_at": profile.created_at,
                "updated_at": profile.updated_at,
                "last_used_at": profile.last_used_at
            }
            profile_list.append(profile_data)
        
        return {
            "profiles": profile_list,
            "total": len(profile_list),
            "voice_model_type": voice_model_type,
            "active_only": active_only
        }
        
    except Exception as e:
        logger.error(f"Failed to list voice profiles: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list voice profiles: {str(e)}"
        )


@router.get("/models")
async def get_available_voice_models(model_type: Optional[str] = None):
    """Get list of all available voice models"""
    models = []
    for model_name, config in VOICE_MODELS.items():
        # Filter by model_type if provided
        config_model_type = config.get("model_type", "asr")
        if model_type and config_model_type != model_type:
            continue
            
        model_info = {
            "model_name": model_name,
            "model_type": config_model_type,
            "requires_api_key": config.get("requires_api_key", True)
        }
        models.append(model_info)
    
    return {
        "models": models,
        "total_models": len(models)
    }


@router.get("/{voice_profile_name}")
async def get_voice_profile(
    voice_profile_name: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Get specific voice profile by name (without API key)"""
    try:
        profile = await VoiceProfileQueries.get_profile(db, voice_profile_name)
        if not profile:
            raise HTTPException(
                status_code=404,
                detail=f"Voice profile '{voice_profile_name}' not found"
            )
        
        return {
            "profile_id": profile.profile_id,
            "voice_profile_name": profile.voice_profile_name,
            "voice_model_type": profile.voice_model_type.value,
            "voice_model_name": profile.voice_model_name,
            "voice_meta_params": profile.voice_meta_params,
            "description": profile.description,
            "is_active": profile.is_active,
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
            "last_used_at": profile.last_used_at
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get voice profile: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get voice profile: {str(e)}"
        )