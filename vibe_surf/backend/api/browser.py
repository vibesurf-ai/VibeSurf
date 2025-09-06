"""
Browser Tabs Router

Handles retrieval of browser tab information including active tab and all tabs.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
import logging

# Import global variables from shared_state
from ..shared_state import browser_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/browser", tags=["browser"])


@router.get("/active-tab")
async def get_active_tab() -> Dict[str, Dict[str, str]]:
    """Get the current active tab information"""
    if not browser_manager:
        raise HTTPException(status_code=503, detail="Browser manager not initialized")
    
    try:
        # Get active tab info using browser manager
        active_tab_info = await browser_manager._get_activate_tab_info()
        
        if not active_tab_info:
            return {}
        
        # Return dict format: {tab_id: {url: , title: }}
        return {
            active_tab_info.target_id[-4:]: {
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
    if not browser_manager:
        raise HTTPException(status_code=503, detail="Browser manager not initialized")
    
    try:
        # Get CDP client from browser manager
        client = browser_manager.main_browser_session.cdp_client
        
        # Get all targets from CDP
        targets_info = await client.send.Target.getTargets()
        
        # Filter only page targets and build result dict
        result = {}
        for target in targets_info["targetInfos"]:
            if target["type"] == "page":
                target_id = target["targetId"]
                
                # Get additional target info for better title if available
                try:
                    target_info = await client.send.Target.getTargetInfo(
                        params={'targetId': target_id}
                    )
                    target_details = target_info.get('targetInfo', target)
                except Exception:
                    target_details = target
                
                result[target_id[-4:]] = {
                    "url": target_details.get('url', ''),
                    "title": target_details.get('title', '')
                }
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get all tabs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get all tabs: {str(e)}")