"""
Agent API endpoints
"""
from typing import List
from fastapi import APIRouter, HTTPException
<<<<<<< HEAD
from vibe_surf.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])
=======

router = APIRouter()
>>>>>>> 85207e53a448ff758ebeadc68121d1765bbc0ce4


@router.get("/get_all_skills", response_model=List[str])
async def get_all_skills():
    """
    Get all available skill names from the VibeSurf tools registry.
    Returns skill names with the 'skill_' prefix removed.
    """
    try:
        from ..shared_state import vibesurf_tools
        if not vibesurf_tools:
            raise HTTPException(status_code=500, detail="VibeSurf tools not initialized")
        
        # Get all action names from the registry
        all_actions = vibesurf_tools.registry.registry.actions.keys()
        
        # Filter for actions that start with 'skill_' and remove the prefix
        skill_names = [
            action_name.replace('skill_', '') 
            for action_name in all_actions 
            if action_name.startswith('skill_')
        ]
<<<<<<< HEAD
        logger.info(skill_names)
=======
        
>>>>>>> 85207e53a448ff758ebeadc68121d1765bbc0ce4
        return skill_names
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get skills: {str(e)}")