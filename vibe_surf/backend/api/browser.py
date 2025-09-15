"""
Browser Tabs Router

Handles retrieval of browser tab information including active tab and all tabs.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
import logging

from vibe_surf.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/browser", tags=["browser"])


@router.get("/active-tab")
async def get_active_tab() -> Dict[str, Dict[str, str]]:
    from ..shared_state import browser_manager
    """Get the current active tab information"""
    if not browser_manager:
        raise HTTPException(status_code=503, detail="Browser manager not initialized")

    try:
        # Get active tab info using browser manager
        active_tab_info = await browser_manager.get_activate_tab()

        if not active_tab_info:
            logger.info("No active tab found!")
            return {}

        logger.info(active_tab_info)
        # Return dict format: {tab_id: {url: , title: }}
        return {
            active_tab_info.target_id[:-4]: {
                "url": active_tab_info.url,
                "title": active_tab_info.title
            }
        }

    except Exception as e:
        logger.error(f"Failed to get active tab: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get active tab: {str(e)}")


@router.get("/all-tabs")
async def get_all_tabs() -> Dict[str, Dict[str, str]]:
    """Get all browser tabs information"""
    from ..shared_state import browser_manager

    if not browser_manager:
        raise HTTPException(status_code=503, detail="Browser manager not initialized")

    try:
        all_tab_infos = await browser_manager.get_all_tabs()

        # Filter only page targets and build result dict
        result = {}
        for tab_info in all_tab_infos:
            result[tab_info.target_id[-4:]] = {
                "url": tab_info.url,
                "title": tab_info.title
            }

        return result

    except Exception as e:
        logger.error(f"Failed to get all tabs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get all tabs: {str(e)}")
