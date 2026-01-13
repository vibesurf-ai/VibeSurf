"""
Chrome Profile Transfer API
Handles browser profile migration from existing Chrome to VibeSurf
"""

import os
import shutil
import platform
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from vibe_surf.logger import get_logger
from ..shared_state import update_envs, get_envs

logger = get_logger(__name__)

router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileTransferRequest(BaseModel):
    """Request model for profile transfer"""
    source_profile_path: Optional[str] = Field(
        None,
        description="Source Chrome profile path. If not provided, will auto-detect default Chrome profile"
    )


class ProfileTransferResponse(BaseModel):
    """Response model for profile transfer"""
    success: bool
    message: str
    transferred_items: Optional[Dict[str, bool]] = None


class ProfileTransferStatusResponse(BaseModel):
    """Response model for profile transfer status"""
    has_transferred: bool
    skip_prompt: bool
    message: str


def get_default_chrome_profile_path() -> Optional[str]:
    """Auto-detect default Chrome profile path based on OS"""
    system = platform.system()

    try:
        if system == 'Darwin':  # macOS
            profile_path = Path.home() / 'Library' / 'Application Support' / 'Google' / 'Chrome' / 'Default'
        elif system == 'Linux':
            profile_path = Path.home() / '.config' / 'google-chrome' / 'Default'
        elif system == 'Windows':
            profile_path = Path.home() / 'AppData' / 'Local' / 'Google' / 'Chrome' / 'User Data' / 'Default'
        else:
            return None

        if profile_path.exists():
            return str(profile_path)
    except Exception as e:
        logger.warning(f"Failed to detect default Chrome profile: {e}")

    return None


def transfer_profile_data(source_path: str, target_path: str) -> Dict[str, bool]:
    """
    Transfer profile data from source to target
    Returns dict of transferred items and their success status
    """
    transferred = {
        'bookmarks': False,
        'history': False,
        'extensions': False,
        'cookies': False,
        'preferences': False
    }

    source_dir = Path(source_path)
    target_dir = Path(target_path)

    # Ensure target directory exists
    target_dir.mkdir(parents=True, exist_ok=True)

    # Define files to transfer
    files_to_transfer = {
        'bookmarks': 'Bookmarks',
        'history': 'History',
        'cookies': 'Cookies',
        'preferences': 'Preferences'
    }

    # Transfer individual files
    for key, filename in files_to_transfer.items():
        source_file = source_dir / filename
        target_file = target_dir / filename

        try:
            if source_file.exists():
                # Backup existing file if it exists
                if target_file.exists():
                    backup_file = target_dir / f"{filename}.backup"
                    shutil.copy2(target_file, backup_file)
                    logger.info(f"Backed up existing {filename} to {backup_file}")

                # Copy the file
                shutil.copy2(source_file, target_file)
                transferred[key] = True
                logger.info(f"Transferred {filename} from {source_file} to {target_file}")
            else:
                logger.warning(f"Source file not found: {source_file}")
        except Exception as e:
            logger.error(f"Failed to transfer {filename}: {e}")
            transferred[key] = False

    # Transfer Extensions directory
    source_extensions = source_dir / 'Extensions'
    target_extensions = target_dir / 'Extensions'

    try:
        if source_extensions.exists() and source_extensions.is_dir():
            if target_extensions.exists():
                backup_extensions = target_dir / 'Extensions.backup'
                if backup_extensions.exists():
                    shutil.rmtree(backup_extensions)
                shutil.copytree(target_extensions, backup_extensions)
                logger.info(f"Backed up existing Extensions to {backup_extensions}")

            # Copy extensions
            if target_extensions.exists():
                shutil.rmtree(target_extensions)
            shutil.copytree(source_extensions, target_extensions)
            transferred['extensions'] = True
            logger.info(f"Transferred Extensions from {source_extensions} to {target_extensions}")
        else:
            logger.warning(f"Source Extensions directory not found: {source_extensions}")
    except Exception as e:
        logger.error(f"Failed to transfer Extensions: {e}")
        transferred['extensions'] = False

    return transferred


@router.get("/transfer-status", response_model=ProfileTransferStatusResponse)
async def get_transfer_status():
    """
    Check if profile has already been transferred
    """
    try:
        envs = get_envs()

        # Check if transfer has been completed
        has_transferred = envs.get("CHROME_PROFILE_TRANSFERRED", "false").lower() == "true"

        # Check if user chose to skip prompt
        skip_prompt = envs.get("CHROME_PROFILE_SKIP_PROMPT", "false").lower() == "true"

        message = "Profile transfer status retrieved successfully"

        return ProfileTransferStatusResponse(
            has_transferred=has_transferred,
            skip_prompt=skip_prompt,
            message=message
        )

    except Exception as e:
        logger.error(f"Failed to get transfer status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transfer", response_model=ProfileTransferResponse)
async def transfer_profile(
    request: ProfileTransferRequest = Body(...)
):
    """
    Transfer Chrome profile data to VibeSurf
    """
    try:
        # Get source profile path
        source_path = request.source_profile_path
        if not source_path:
            # Auto-detect default Chrome profile
            source_path = get_default_chrome_profile_path()
            if not source_path:
                raise HTTPException(
                    status_code=400,
                    detail="Could not auto-detect Chrome profile. Please provide source_profile_path."
                )

        # Validate source path
        if not os.path.exists(source_path):
            raise HTTPException(
                status_code=400,
                detail=f"Source profile path does not exist: {source_path}"
            )

        # Get target profile path from environment
        envs = get_envs()
        target_path = envs.get("BROWSER_USER_DATA")

        if not target_path:
            raise HTTPException(
                status_code=500,
                detail="BROWSER_USER_DATA not configured"
            )

        logger.info(f"Starting profile transfer from {source_path} to {target_path}")

        # Perform transfer
        transferred_items = transfer_profile_data(source_path, target_path)

        # Update environment variables to mark transfer as complete
        update_envs({
            "CHROME_PROFILE_TRANSFERRED": "true",
            "CHROME_PROFILE_SOURCE": source_path
        })

        success_count = sum(1 for v in transferred_items.values() if v)
        total_count = len(transferred_items)

        return ProfileTransferResponse(
            success=success_count > 0,
            message=f"Profile transfer completed: {success_count}/{total_count} items transferred successfully",
            transferred_items=transferred_items
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile transfer failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skip-transfer")
async def skip_transfer():
    """
    Mark that user chose to skip profile transfer and not show prompt again
    """
    try:
        # Update environment variables to skip prompt in future
        update_envs({
            "CHROME_PROFILE_SKIP_PROMPT": "true"
        })

        return {
            "success": True,
            "message": "Profile transfer prompt will not be shown again"
        }

    except Exception as e:
        logger.error(f"Failed to skip transfer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancel-skip")
async def cancel_skip():
    """
    Re-enable profile transfer prompt (for testing or if user changes mind)
    """
    try:
        # Update environment variables to show prompt again
        update_envs({
            "CHROME_PROFILE_SKIP_PROMPT": "false"
        })

        return {
            "success": True,
            "message": "Profile transfer prompt re-enabled"
        }

    except Exception as e:
        logger.error(f"Failed to cancel skip: {e}")
        raise HTTPException(status_code=500, detail=str(e))
